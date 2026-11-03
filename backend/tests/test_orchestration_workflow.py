import importlib

import pytest

from app.models.workflow import AgentExecution
from app.orchestration.execution_manager import ExecutionManager
from app.orchestration.orchestrator import CentralAgentOrchestrator
from app.orchestration.workflow_context import WorkflowContext
from app.orchestration.workflow_engine import WorkflowEngine


def _create_isolated_execution_manager(tmp_path, monkeypatch):
    db_path = tmp_path / "atomicity.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    import app.database as database_module
    import app.models.workflow as workflow_module
    import app.orchestration.execution_manager as execution_manager_module

    importlib.reload(database_module)
    importlib.reload(workflow_module)
    importlib.reload(execution_manager_module)

    manager = execution_manager_module.ExecutionManager(session_factory=database_module.SessionLocal)
    return manager


def test_orchestrator_runs_research_and_creative_agents():
    orchestrator = CentralAgentOrchestrator()
    context = orchestrator.run(
        creator_id=1,
        campaign_topic="creator growth",
        target_audience="new creators",
        platforms=["Instagram", "YouTube"],
        campaign_objective="build trusted educational content",
        content_type="short-form",
        competitor_urls=["https://example.com/competitor-one"],
        rss_sources=["https://example.com/rss-one"],
        creator_writing_samples=["I help creators build repeatable systems and clarity."],
    )

    assert isinstance(context, WorkflowContext)
    assert context.workflow_id is not None
    assert context.agent_records
    assert "Trend Research Agent" in context.agent_records
    assert "Hook Generation Agent" in context.agent_records
    assert context.approval_status == "PENDING"


def test_workflow_context_tracks_generated_outputs():
    orchestrator = CentralAgentOrchestrator()
    context = orchestrator.run(
        campaign_topic="AI for creators",
        platforms=["Instagram"],
        competitor_urls=[],
        rss_sources=[],
        creator_writing_samples=["Systematic content wins over random inspiration."],
    )

    assert context.research_findings
    assert context.brand_voice["voice_profile"]
    assert context.hooks
    assert context.creative_output["platform"] in {"Instagram", "YouTube", "LinkedIn"}


def test_workflow_checkpoint_persists_successful_agent_outputs():
    orchestrator = CentralAgentOrchestrator()
    context = orchestrator.run(
        campaign_topic="AI content systems",
        platforms=["Instagram"],
        competitor_urls=["https://example.com/alpha"],
        rss_sources=["https://example.com/rss-alpha"],
        creator_writing_samples=["Clarity compounds. Systems are scalable."],
    )

    workflow = ExecutionManager().get_workflow(context.workflow_id)
    assert workflow is not None
    assert workflow.checkpoint_data
    assert workflow.last_successful_agent in {"Publishing and Scheduling Agent", "COMPLETED"}
    assert workflow.checkpoint_data["agent_records"]["Trend Research Agent"]["status"].upper() == "COMPLETED"


def test_workflow_context_can_be_restored_from_checkpoint():
    orchestrator = CentralAgentOrchestrator()
    context = orchestrator.run(
        campaign_topic="creator trust",
        platforms=["YouTube"],
        competitor_urls=[],
        rss_sources=["https://example.com/rss-trust"],
        creator_writing_samples=["Trust grows through relevance and consistency."],
    )

    restored = ExecutionManager().get_workflow_context(context.workflow_id)
    assert restored is not None
    assert restored.workflow_id == context.workflow_id
    assert restored.campaign_topic == "creator trust"
    assert restored.hooks
    assert restored.brand_voice["voice_profile"]


def test_checkpoint_keeps_prior_success_after_later_agent_fails():
    class FailingAgent:
        name = "Failing Agent"

        def execute(self, **kwargs):
            raise RuntimeError("simulated failure after successful checkpoint")

    class SuccessAgent:
        name = "Trend Research Agent"

        def execute(self, **kwargs):
            return {
                "status": "completed",
                "ranked_topic_suggestions": [{"title": "creator systems", "score": 92}],
                "source_urls": ["https://example.com/rss-prior"],
            }

    class DummyRegistry:
        def register_default_agents(self):
            return None

        def execution_order(self):
            return ["Trend Research Agent", "Failing Agent"]

        def get(self, name):
            if name == "Trend Research Agent":
                return SuccessAgent()
            if name == "Failing Agent":
                return FailingAgent()
            raise KeyError(name)

    engine = WorkflowEngine(registry=DummyRegistry())
    context = WorkflowContext(campaign_topic="reliable creative loops", platforms=["Instagram"])
    result = engine.run(context)

    workflow = ExecutionManager().get_workflow(result.workflow_id)
    assert workflow is not None
    assert workflow.status == "FAILED"
    assert workflow.checkpoint_data["agent_records"]["Trend Research Agent"]["ranked_topic_suggestions"][0]["title"] == "creator systems"
    assert result.error_message == "simulated failure after successful checkpoint"


def test_successful_agent_execution_commits_checkpoint_and_completion_status(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)

    class SuccessAgent:
        name = "Trend Research Agent"

        def execute(self, **kwargs):
            return {
                "status": "completed",
                "ranked_topic_suggestions": [{"title": "systems", "score": 91}],
                "source_urls": ["https://example.com/rss-success"],
            }

    class DummyRegistry:
        def register_default_agents(self):
            return None

        def execution_order(self):
            return ["Trend Research Agent"]

        def get(self, name):
            return SuccessAgent()

    context = WorkflowContext(campaign_topic="repeatable systems", platforms=["Instagram"])
    engine = WorkflowEngine(registry=DummyRegistry(), execution_manager=manager)
    result = engine.run(context)

    workflow = manager.get_workflow(result.workflow_id)
    assert workflow is not None
    assert workflow.status == "COMPLETED"
    assert workflow.checkpoint_data["agent_records"]["Trend Research Agent"]["status"].upper() == "COMPLETED"
    assert workflow.last_successful_agent == "COMPLETED"


def test_final_checkpoint_failure_does_not_persist_false_success(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)

    class SuccessAgent:
        name = "Trend Research Agent"

        def execute(self, **kwargs):
            return {
                "status": "completed",
                "ranked_topic_suggestions": [{"title": "creative loops", "score": 88}],
                "source_urls": ["https://example.com/rss-atomic"],
            }

    class DummyRegistry:
        def register_default_agents(self):
            return None

        def execution_order(self):
            return ["Trend Research Agent"]

        def get(self, name):
            return SuccessAgent()

    engine = WorkflowEngine(registry=DummyRegistry(), execution_manager=manager)
    original = manager.save_workflow_checkpoint

    def broken_save(workflow_id, context, agent_name=None, status=None, error_message=None, execution_summary=None):
        if agent_name == "COMPLETED":
            raise RuntimeError("simulated final checkpoint failure")
        return original(
            workflow_id,
            context,
            agent_name=agent_name,
            status=status,
            error_message=error_message,
            execution_summary=execution_summary,
        )

    manager.save_workflow_checkpoint = broken_save
    context = WorkflowContext(campaign_topic="atomic checkpoints", platforms=["Instagram"])

    with pytest.raises(RuntimeError, match="simulated final checkpoint failure"):
        engine.run(context)

    workflow = manager.get_workflow(context.workflow_id)
    assert workflow is not None
    assert workflow.status == "FAILED"
    assert "simulated final checkpoint failure" in workflow.error_message
    assert workflow.checkpoint_data["agent_records"]["Trend Research Agent"]["ranked_topic_suggestions"][0]["title"] == "creative loops"
    assert workflow.checkpoint_data["agent_records"]["Trend Research Agent"]["status"].upper() == "COMPLETED"


def test_agent_execution_remains_running_until_checkpoint_commit_succeeds(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)

    class SuccessAgent:
        name = "Trend Research Agent"

        def execute(self, **kwargs):
            return {
                "status": "completed",
                "ranked_topic_suggestions": [{"title": "checkpoint order", "score": 95}],
                "source_urls": ["https://example.com/rss-order"],
            }

    class DummyRegistry:
        def register_default_agents(self):
            return None

        def execution_order(self):
            return ["Trend Research Agent"]

        def get(self, name):
            return SuccessAgent()

    original_save = manager.save_workflow_checkpoint
    observed = {}

    def guarded_save(workflow_id, context, agent_name=None, status=None, error_message=None, execution_summary=None):
        if agent_name == "Trend Research Agent":
            execution = manager.get_agent_execution(workflow_id, "Trend Research Agent")
            observed["during_save"] = execution.status if execution is not None else None
        return original_save(
            workflow_id,
            context,
            agent_name=agent_name,
            status=status,
            error_message=error_message,
            execution_summary=execution_summary,
        )

    manager.save_workflow_checkpoint = guarded_save
    engine = WorkflowEngine(registry=DummyRegistry(), execution_manager=manager)
    context = WorkflowContext(campaign_topic="checkpoint sequencing", platforms=["Instagram"])
    result = engine.run(context)

    execution = manager.get_agent_execution(result.workflow_id, "Trend Research Agent")
    assert observed["during_save"] == "RUNNING"
    assert execution is not None
    assert execution.status == "COMPLETED"


def test_checkpoint_failure_marks_corresponding_agent_execution_failed(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)

    class SuccessAgent:
        name = "Trend Research Agent"

        def execute(self, **kwargs):
            return {
                "status": "completed",
                "ranked_topic_suggestions": [{"title": "failed checkpoint", "score": 80}],
                "source_urls": ["https://example.com/rss-failure"],
            }

    class DummyRegistry:
        def register_default_agents(self):
            return None

        def execution_order(self):
            return ["Trend Research Agent"]

        def get(self, name):
            return SuccessAgent()

    original_save = manager.save_workflow_checkpoint

    def broken_save(workflow_id, context, agent_name=None, status=None, error_message=None, execution_summary=None):
        if agent_name == "Trend Research Agent":
            raise RuntimeError("simulated save failure")
        return original_save(
            workflow_id,
            context,
            agent_name=agent_name,
            status=status,
            error_message=error_message,
            execution_summary=execution_summary,
        )

    manager.save_workflow_checkpoint = broken_save
    engine = WorkflowEngine(registry=DummyRegistry(), execution_manager=manager)
    context = WorkflowContext(campaign_topic="persisted failure", platforms=["Instagram"])

    with pytest.raises(RuntimeError, match="simulated save failure"):
        engine.run(context)

    workflow = manager.get_workflow(context.workflow_id)
    assert workflow is not None
    assert workflow.status == "FAILED"
    execution = manager.get_agent_execution(workflow.id, "Trend Research Agent")
    assert execution is not None
    assert execution.status == "FAILED"
    assert "simulated save failure" in execution.error_message


def test_no_agent_execution_row_stays_completed_when_checkpoint_failed(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)

    class SuccessAgent:
        name = "Trend Research Agent"

        def execute(self, **kwargs):
            return {
                "status": "completed",
                "ranked_topic_suggestions": [{"title": "no completed leak", "score": 74}],
                "source_urls": ["https://example.com/rss-leak"],
            }

    class DummyRegistry:
        def register_default_agents(self):
            return None

        def execution_order(self):
            return ["Trend Research Agent"]

        def get(self, name):
            return SuccessAgent()

    original_save = manager.save_workflow_checkpoint

    def broken_save(workflow_id, context, agent_name=None, status=None, error_message=None, execution_summary=None):
        if agent_name == "Trend Research Agent":
            raise RuntimeError("simulated checkpoint leak")
        return original_save(
            workflow_id,
            context,
            agent_name=agent_name,
            status=status,
            error_message=error_message,
            execution_summary=execution_summary,
        )

    manager.save_workflow_checkpoint = broken_save
    engine = WorkflowEngine(registry=DummyRegistry(), execution_manager=manager)
    context = WorkflowContext(campaign_topic="checkpoint leak guard", platforms=["Instagram"])

    with pytest.raises(RuntimeError, match="simulated checkpoint leak"):
        engine.run(context)

    with manager.session_factory() as session:
        rows = session.query(AgentExecution).filter_by(workflow_id=context.workflow_id).all()
    assert rows
    assert all(row.status != "COMPLETED" for row in rows)
