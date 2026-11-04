import importlib
from datetime import datetime

import pytest
from sqlalchemy import text

from app.models.workflow import AgentExecution, Workflow
from app.orchestration.execution_manager import ExecutionManager
from app.orchestration.orchestrator import CentralAgentOrchestrator
from app.orchestration.workflow_context import WorkflowContext
from app.orchestration.workflow_engine import WorkflowEngine
from app.routers.orchestration import WorkflowApprovalRequest, approve_workflow


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
    assert workflow.last_successful_agent in {"Video Production Agent", "Publishing and Scheduling Agent", "COMPLETED"}
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
    assert workflow.status == "WAITING_FOR_APPROVAL"
    assert workflow.checkpoint_data["agent_records"]["Trend Research Agent"]["status"].upper() == "COMPLETED"
    assert workflow.last_successful_agent == "COMPLETED"


def test_pending_approval_blocks_scheduling_and_preserves_last_successful_agent(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)

    class SuccessAgent:
        name = "Trend Research Agent"

        def execute(self, **kwargs):
            return {
                "status": "completed",
                "ranked_topic_suggestions": [{"title": "creative loops", "score": 88}],
                "source_urls": ["https://example.com/rss-approval"],
            }

    class DummyRegistry:
        def register_default_agents(self):
            return None

        def execution_order(self):
            return ["Trend Research Agent", "Publishing and Scheduling Agent"]

        def get(self, name):
            if name == "Trend Research Agent":
                return SuccessAgent()
            raise KeyError(name)

    engine = WorkflowEngine(registry=DummyRegistry(), execution_manager=manager)
    context = WorkflowContext(campaign_topic="approval gating", platforms=["Instagram"])
    result = engine.run(context)

    workflow = manager.get_workflow(result.workflow_id)
    assert workflow is not None
    assert workflow.status == "WAITING_FOR_APPROVAL"
    assert workflow.last_successful_agent == "Trend Research Agent"
    assert result.approval_status == "PENDING"


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


def test_resume_workflow_retries_only_failed_agent_and_preserves_completed_outputs(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)

    class FirstSuccessAgent:
        name = "Trend Research Agent"
        calls = 0

        def execute(self, **kwargs):
            type(self).calls += 1
            return {
                "status": "completed",
                "ranked_topic_suggestions": [{"title": "initial topic", "score": 91}],
                "source_urls": ["https://example.com/rss-resume"],
            }

    class FlakyAgent:
        calls = 0

        def execute(self, **kwargs):
            type(self).calls += 1
            if type(self).calls == 1:
                raise RuntimeError("retry required")
            return {"status": "completed", "hook_alternatives": ["Resume after retry"]}

    class FinalSuccessAgent:
        name = "Hook Generation Agent"
        calls = 0

        def execute(self, **kwargs):
            type(self).calls += 1
            return {"status": "completed", "hook_alternatives": ["Recovered hook"]}

    class DummyRegistry:
        def register_default_agents(self):
            return None

        def execution_order(self):
            return ["Trend Research Agent", "Failing Agent", "Hook Generation Agent"]

        def get(self, name):
            if name == "Trend Research Agent":
                return FirstSuccessAgent()
            if name == "Failing Agent":
                return FlakyAgent()
            if name == "Hook Generation Agent":
                return FinalSuccessAgent()
            raise KeyError(name)

    engine = WorkflowEngine(registry=DummyRegistry(), execution_manager=manager)
    context = WorkflowContext(campaign_topic="retry resume", platforms=["Instagram"])
    result = engine.run(context)

    workflow = manager.get_workflow(context.workflow_id)
    assert workflow is not None
    assert workflow.status == "FAILED"
    assert result.error_message == "retry required"

    resumed = engine.resume_workflow(workflow.id)
    assert resumed.workflow_id == workflow.id
    assert resumed.hooks == ["Recovered hook"]
    assert FirstSuccessAgent.calls == 1
    assert FlakyAgent.calls == 2
    assert FinalSuccessAgent.calls == 1


def test_retry_count_increments_when_retry_attempt_starts(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)

    class SuccessAgent:
        def execute(self, **kwargs):
            return {"status": "completed", "ranked_topic_suggestions": [{"title": "stable topic", "score": 90}], "source_urls": ["https://example.com/rss-retry"]}

    class FlakyAgent:
        calls = 0

        def execute(self, **kwargs):
            type(self).calls += 1
            if type(self).calls == 1:
                raise RuntimeError("need retry")
            return {"status": "completed", "hook_alternatives": ["recovered hook"]}

    class DummyRegistry:
        def register_default_agents(self):
            return None

        def execution_order(self):
            return ["Trend Research Agent", "Failing Agent"]

        def get(self, name):
            if name == "Trend Research Agent":
                return SuccessAgent()
            if name == "Failing Agent":
                return FlakyAgent()
            raise KeyError(name)

    engine = WorkflowEngine(registry=DummyRegistry(), execution_manager=manager)
    context = WorkflowContext(campaign_topic="retry counts", platforms=["Instagram"])
    result = engine.run(context)

    workflow = manager.get_workflow(context.workflow_id)
    assert workflow is not None
    assert workflow.status == "FAILED"
    assert result.error_message == "need retry"

    resumed = engine.resume_workflow(workflow.id)
    execution = manager.get_agent_execution(workflow.id, "Failing Agent")
    assert execution is not None
    assert execution.status == "COMPLETED"
    assert execution.retry_count == 1
    assert execution.output_data["hook_alternatives"] == ["recovered hook"]
    assert resumed.workflow_id == workflow.id


def test_retry_limit_is_enforced_before_retry_is_allowed(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)

    class SuccessAgent:
        def execute(self, **kwargs):
            return {"status": "completed", "ranked_topic_suggestions": [{"title": "limit topic", "score": 80}], "source_urls": ["https://example.com/rss-limit"]}

    class FlakyAgent:
        calls = 0

        def execute(self, **kwargs):
            type(self).calls += 1
            raise RuntimeError("limit reached")

    class DummyRegistry:
        def register_default_agents(self):
            return None

        def execution_order(self):
            return ["Trend Research Agent", "Failing Agent"]

        def get(self, name):
            if name == "Trend Research Agent":
                return SuccessAgent()
            if name == "Failing Agent":
                return FlakyAgent()
            raise KeyError(name)

    engine = WorkflowEngine(registry=DummyRegistry(), execution_manager=manager)
    context = WorkflowContext(campaign_topic="retry limit", platforms=["Instagram"])
    result = engine.run(context)

    workflow = manager.get_workflow(context.workflow_id)
    assert workflow is not None
    assert workflow.status == "FAILED"
    assert result.error_message == "limit reached"

    with manager.session_factory() as session:
        execution = session.query(AgentExecution).filter_by(workflow_id=workflow.id, agent_name="Failing Agent").order_by(AgentExecution.id.desc()).first()
        execution.retry_count = 1
        session.commit()

    with pytest.raises(RuntimeError, match="Retry limit of 1 reached"):
        engine.resume_workflow(workflow.id, retry_limit=1)

    execution = manager.get_agent_execution(workflow.id, "Failing Agent")
    assert execution is not None
    assert execution.retry_count == 1


def test_unknown_approval_status_is_rejected(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)
    context = WorkflowContext(campaign_topic="unknown approval", platforms=["Instagram"])
    engine = WorkflowEngine(execution_manager=manager)
    workflow = manager.create_workflow(context)

    with manager.session_factory() as session:
        wf = session.get(Workflow, workflow.id)
        wf.approval_status = "UNKNOWN"
        wf.approval_content_hash = WorkflowEngine._content_fingerprint(context)
        session.commit()

    with pytest.raises(RuntimeError, match="Human approval is required before resume"):
        engine._enforce_approval_gate(workflow.id, context, action="resume")


def test_approved_workflow_with_missing_persisted_fingerprint_is_rejected(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)
    context = WorkflowContext(campaign_topic="missing hash", platforms=["Instagram"])
    engine = WorkflowEngine(execution_manager=manager)
    workflow = manager.create_workflow(context)

    with manager.session_factory() as session:
        wf = session.get(Workflow, workflow.id)
        wf.approval_status = "APPROVED"
        wf.approval_content_hash = None
        session.commit()

    context.approval_status = "APPROVED"
    context.approval_content_hash = WorkflowEngine._content_fingerprint(context)

    with pytest.raises(RuntimeError, match="missing a persisted content fingerprint"):
        engine._enforce_approval_gate(workflow.id, context, action="resume")


def test_database_approval_status_must_be_approved_even_if_context_is_approved(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)
    context = WorkflowContext(campaign_topic="database approval guard", platforms=["Instagram"])
    engine = WorkflowEngine(execution_manager=manager)
    workflow = manager.create_workflow(context)
    fingerprint = WorkflowEngine._content_fingerprint(context)

    with manager.session_factory() as session:
        session.execute(text("UPDATE workflows SET approval_status = :status, approval_content_hash = :hash WHERE id = :id"), {"status": "", "hash": fingerprint, "id": workflow.id})
        session.commit()

    context.approval_status = "APPROVED"
    context.approval_content_hash = fingerprint

    with pytest.raises(RuntimeError, match="Human approval is required before resume"):
        engine._enforce_approval_gate(workflow.id, context, action="resume")


def test_content_modified_after_approval_is_rejected(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)
    context = WorkflowContext(campaign_topic="original approval", platforms=["Instagram"])
    engine = WorkflowEngine(execution_manager=manager)
    workflow = manager.create_workflow(context)
    context.approval_status = "APPROVED"
    context.approval_content_hash = WorkflowEngine._content_fingerprint(context)

    with manager.session_factory() as session:
        wf = session.get(Workflow, workflow.id)
        wf.approval_status = "APPROVED"
        wf.approval_content_hash = context.approval_content_hash
        session.commit()

    context.campaign_topic = "changed after approval"
    with pytest.raises(RuntimeError, match="Content was changed after approval; a fresh human approval is required"):
        engine._enforce_approval_gate(workflow.id, context, action="resume")


def test_stale_context_fingerprint_is_rejected(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)
    context = WorkflowContext(campaign_topic="stale context", platforms=["Instagram"])
    engine = WorkflowEngine(execution_manager=manager)
    workflow = manager.create_workflow(context)
    hash_value = WorkflowEngine._content_fingerprint(context)

    with manager.session_factory() as session:
        wf = session.get(Workflow, workflow.id)
        wf.approval_status = "APPROVED"
        wf.approval_content_hash = hash_value
        session.commit()

    context.approval_status = "APPROVED"
    context.approval_content_hash = "stale-hash"

    with pytest.raises(RuntimeError, match="Workflow approval does not match the current content version"):
        engine._enforce_approval_gate(workflow.id, context, action="resume")


def test_request_changes_followed_by_resume_is_blocked(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)
    context = WorkflowContext(campaign_topic="requested changes", platforms=["Instagram"])
    engine = WorkflowEngine(execution_manager=manager)
    workflow = manager.create_workflow(context)
    hash_value = WorkflowEngine._content_fingerprint(context)

    with manager.session_factory() as session:
        wf = session.get(Workflow, workflow.id)
        wf.status = "WAITING_FOR_APPROVAL"
        wf.approval_status = "REQUESTED_CHANGES"
        wf.approval_content_hash = hash_value
        session.commit()

    with pytest.raises(RuntimeError, match="waiting for human approval before it can resume"):
        engine.resume_workflow(workflow.id)


def test_valid_approved_workflow_can_resume_successfully(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)

    class SuccessAgent:
        name = "Trend Research Agent"

        def execute(self, **kwargs):
            return {
                "status": "completed",
                "ranked_topic_suggestions": [{"title": "resumable topic", "score": 97}],
                "source_urls": ["https://example.com/rss-resume-valid"],
            }

    class PublishAgent:
        name = "Publishing and Scheduling Agent"

        def execute(self, **kwargs):
            return {"status": "completed"}

    class DummyRegistry:
        def register_default_agents(self):
            return None

        def execution_order(self):
            return ["Trend Research Agent", "Publishing and Scheduling Agent"]

        def get(self, name):
            if name == "Trend Research Agent":
                return SuccessAgent()
            if name == "Publishing and Scheduling Agent":
                return PublishAgent()
            raise KeyError(name)

    context = WorkflowContext(campaign_topic="approved resume", platforms=["Instagram"])
    workflow = manager.create_workflow(context)
    hash_value = WorkflowEngine._content_fingerprint(context)

    with manager.session_factory() as session:
        wf = session.get(Workflow, workflow.id)
        wf.status = "APPROVED"
        wf.approval_status = "APPROVED"
        wf.approval_content_hash = hash_value
        session.commit()

    engine = WorkflowEngine(registry=DummyRegistry(), execution_manager=manager)
    resumed = engine.resume_workflow(workflow.id)
    assert resumed.workflow_id == workflow.id


def test_scheduling_boundary_rejects_persisted_approval_mismatch_and_never_executes_publish_agent(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)
    publish_calls = {"count": 0}

    class SuccessAgent:
        name = "Trend Research Agent"

        def execute(self, **kwargs):
            return {
                "status": "completed",
                "ranked_topic_suggestions": [{"title": "publish blocked", "score": 90}],
                "source_urls": ["https://example.com/rss-publish-blocked"],
            }

    class PublishAgent:
        name = "Publishing and Scheduling Agent"

        def execute(self, **kwargs):
            publish_calls["count"] += 1
            return {"status": "completed"}

    class DummyRegistry:
        def register_default_agents(self):
            return None

        def execution_order(self):
            return ["Trend Research Agent", "Publishing and Scheduling Agent"]

        def get(self, name):
            if name == "Trend Research Agent":
                return SuccessAgent()
            if name == "Publishing and Scheduling Agent":
                return PublishAgent()
            raise KeyError(name)

    engine = WorkflowEngine(registry=DummyRegistry(), execution_manager=manager)
    context = WorkflowContext(campaign_topic="publish guard", platforms=["Instagram"])
    workflow = manager.create_workflow(context)

    with manager.session_factory() as session:
        wf = session.get(Workflow, workflow.id)
        wf.approval_status = "APPROVED"
        wf.approval_content_hash = "mismatched-persisted-hash"
        session.commit()

    context.approval_status = "APPROVED"
    context.approval_content_hash = "stale-context-hash"

    with pytest.raises(RuntimeError, match="Content was changed after approval|Workflow approval does not match the current content version"):
        engine._block_before_scheduling(workflow.id, context, agent_name="Publishing and Scheduling Agent")

    assert publish_calls["count"] == 0

    persisted = manager.get_workflow(workflow.id)
    assert persisted is not None
    assert persisted.approval_status == "APPROVED"
    assert persisted.approval_content_hash == "mismatched-persisted-hash"


def test_enforce_approval_gate_raises_when_workflow_record_is_missing(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)

    class DummyRegistry:
        def register_default_agents(self):
            return None

        def execution_order(self):
            return []

        def get(self, name):
            raise KeyError(name)

    engine = WorkflowEngine(registry=DummyRegistry(), execution_manager=manager)
    missing_context = WorkflowContext(campaign_topic="missing workflow", platforms=["Instagram"])

    with pytest.raises(RuntimeError, match="Workflow .* was not found; human approval cannot be bypassed"):
        engine._enforce_approval_gate(999999, missing_context, action="resume")


def test_workflow_waits_for_human_approval_after_generation(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)

    class SuccessAgent:
        name = "Trend Research Agent"

        def execute(self, **kwargs):
            return {
                "status": "completed",
                "ranked_topic_suggestions": [{"title": "approval gate", "score": 90}],
                "source_urls": ["https://example.com/rss-approval"],
            }

    class DummyRegistry:
        def register_default_agents(self):
            return None

        def execution_order(self):
            return ["Trend Research Agent"]

        def get(self, name):
            return SuccessAgent()

    context = WorkflowContext(campaign_topic="approval gate", platforms=["Instagram"])
    engine = WorkflowEngine(registry=DummyRegistry(), execution_manager=manager)
    result = engine.run(context)

    workflow = manager.get_workflow(result.workflow_id)
    assert workflow is not None
    assert workflow.status == "WAITING_FOR_APPROVAL"
    assert result.approval_status == "PENDING"
    assert workflow.approval_status == "PENDING"


def test_workflow_approval_persists_and_matches_content_version(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)

    class SuccessAgent:
        name = "Trend Research Agent"

        def execute(self, **kwargs):
            return {
                "status": "completed",
                "ranked_topic_suggestions": [{"title": "approved topic", "score": 93}],
                "source_urls": ["https://example.com/rss-approved"],
            }

    class DummyRegistry:
        def register_default_agents(self):
            return None

        def execution_order(self):
            return ["Trend Research Agent"]

        def get(self, name):
            return SuccessAgent()

    context = WorkflowContext(campaign_topic="approved topic", platforms=["Instagram"])
    engine = WorkflowEngine(registry=DummyRegistry(), execution_manager=manager)
    result = engine.run(context)

    workflow = manager.get_workflow(result.workflow_id)
    assert workflow is not None
    assert workflow.status == "WAITING_FOR_APPROVAL"

    manager.record_approval_decision(
        workflow.id,
        "APPROVED",
        approved_by="reviewer",
        notes="Looks good.",
        content_hash=WorkflowEngine._content_fingerprint(result),
    )

    workflow = manager.get_workflow(workflow.id)
    assert workflow is not None
    assert workflow.status == "APPROVED"
    assert workflow.approval_status == "APPROVED"
    assert workflow.approved_by == "reviewer"


def test_rejected_workflow_cannot_resume_until_new_approval(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)

    class SuccessAgent:
        name = "Trend Research Agent"

        def execute(self, **kwargs):
            return {
                "status": "completed",
                "ranked_topic_suggestions": [{"title": "rejected topic", "score": 82}],
                "source_urls": ["https://example.com/rss-rejected"],
            }

    class DummyRegistry:
        def register_default_agents(self):
            return None

        def execution_order(self):
            return ["Trend Research Agent"]

        def get(self, name):
            return SuccessAgent()

    context = WorkflowContext(campaign_topic="rejected topic", platforms=["Instagram"])
    engine = WorkflowEngine(registry=DummyRegistry(), execution_manager=manager)
    result = engine.run(context)

    workflow = manager.get_workflow(result.workflow_id)
    manager.record_approval_decision(workflow.id, "REJECTED", approved_by="reviewer", notes="Needs work.")

    with pytest.raises(RuntimeError, match="not eligible for retry|waiting for human approval"):
        engine.resume_workflow(workflow.id)

    workflow = manager.get_workflow(workflow.id)
    assert workflow.status == "REJECTED"


def test_scheduling_integrity_failure_does_not_overwrite_valid_approval(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)
    context = WorkflowContext(campaign_topic="approval integrity", platforms=["Instagram"])
    engine = WorkflowEngine(execution_manager=manager)
    workflow = manager.create_workflow(context)
    valid_hash = WorkflowEngine._content_fingerprint(context)

    with manager.session_factory() as session:
        wf = session.get(Workflow, workflow.id)
        wf.approval_status = "APPROVED"
        wf.approval_content_hash = valid_hash
        wf.approved_by = "reviewer"
        session.commit()

    context.approval_status = "APPROVED"
    context.approval_content_hash = "stale-hash"

    with pytest.raises(RuntimeError, match="Workflow approval does not match the current content version"):
        engine._block_before_scheduling(workflow.id, context, agent_name="Publishing and Scheduling Agent")

    persisted = manager.get_workflow(workflow.id)
    assert persisted is not None
    assert persisted.approval_status == "APPROVED"
    assert persisted.approval_content_hash == valid_hash
    assert persisted.approved_by == "reviewer"


def test_missing_workflow_remains_a_failure_for_scheduling_guard(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)
    context = WorkflowContext(campaign_topic="missing workflow schedule guard", platforms=["Instagram"])
    engine = WorkflowEngine(execution_manager=manager)

    with pytest.raises(RuntimeError, match="Workflow .* was not found; human approval cannot be bypassed"):
        engine._block_before_scheduling(999999, context, agent_name="Publishing and Scheduling Agent")


def test_checkpoint_save_cannot_overwrite_valid_approval_metadata(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)
    context = WorkflowContext(campaign_topic="checkpoint approval guard", platforms=["Instagram"])
    workflow = manager.create_workflow(context)
    valid_hash = WorkflowEngine._content_fingerprint(context)

    with manager.session_factory() as session:
        wf = session.get(Workflow, workflow.id)
        wf.approval_status = "APPROVED"
        wf.approval_content_hash = valid_hash
        wf.approved_by = "valid-reviewer"
        wf.approval_notes = "Looks good"
        session.commit()

    stale_context = WorkflowContext(campaign_topic="checkpoint approval guard", platforms=["Instagram"])
    stale_context.approval_status = "PENDING"
    stale_context.approval_content_hash = "stale-hash"
    stale_context.approval_notes = "stale notes"
    stale_context.approved_by = "stale-reviewer"
    stale_context.content_version = 99

    manager.save_workflow_checkpoint(workflow.id, stale_context, agent_name="Trend Research Agent", status="RUNNING")

    persisted = manager.get_workflow(workflow.id)
    assert persisted is not None
    assert persisted.approval_status == "APPROVED"
    assert persisted.approval_content_hash == valid_hash
    assert persisted.approval_notes == "Looks good"
    assert persisted.approved_by == "valid-reviewer"


def test_approve_workflow_records_current_content_fingerprint(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)
    context = WorkflowContext(campaign_topic="approved content fingerprint", platforms=["Instagram"])
    workflow = manager.create_workflow(context)

    with manager.session_factory() as session:
        wf = session.get(Workflow, workflow.id)
        wf.status = "WAITING_FOR_APPROVAL"
        wf.approval_status = "PENDING"
        wf.approval_content_hash = None
        session.commit()

    response = approve_workflow(
        workflow.id,
        WorkflowApprovalRequest(approved_by="human-reviewer", notes="Looks good."),
    )

    assert response["status"] == "APPROVED"
    persisted = manager.get_workflow(workflow.id)
    assert persisted is not None
    assert persisted.approval_status == "APPROVED"
    assert persisted.approval_content_hash == WorkflowEngine()._content_fingerprint(manager.get_workflow_context(workflow.id))
    assert persisted.status == "APPROVED"


def test_approve_workflow_persists_request_payload_values_and_current_fingerprint(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)
    context = WorkflowContext(campaign_topic="api approval values", platforms=["Instagram"])
    workflow = manager.create_workflow(context)

    with manager.session_factory() as session:
        wf = session.get(Workflow, workflow.id)
        wf.status = "WAITING_FOR_APPROVAL"
        wf.approval_status = "PENDING"
        wf.approval_content_hash = None
        session.commit()

    response = approve_workflow(
        workflow.id,
        WorkflowApprovalRequest(approved_by="reviewer-007", notes="Approved with specific reviewer notes."),
    )

    assert response["status"] == "APPROVED"
    persisted = manager.get_workflow(workflow.id)
    assert persisted is not None
    assert persisted.approved_by == "reviewer-007"
    assert persisted.approval_notes == "Approved with specific reviewer notes."
    assert persisted.approval_status == "APPROVED"
    assert persisted.approval_content_hash == WorkflowEngine()._content_fingerprint(manager.get_workflow_context(workflow.id))
    assert response["context"]["approved_by"] == "reviewer-007"
    assert response["context"]["approval_notes"] == "Approved with specific reviewer notes."
    assert response["context"]["approval_content_hash"] == persisted.approval_content_hash


def test_checkpoint_save_does_not_restore_missing_approved_hash_and_request_changes_invalidate_approval(tmp_path, monkeypatch):
    manager = _create_isolated_execution_manager(tmp_path, monkeypatch)
    context = WorkflowContext(campaign_topic="approval invalidation", platforms=["Instagram"])
    workflow = manager.create_workflow(context)
    valid_hash = WorkflowEngine._content_fingerprint(context)

    with manager.session_factory() as session:
        wf = session.get(Workflow, workflow.id)
        wf.approval_status = "APPROVED"
        wf.approval_content_hash = None
        wf.approved_at = datetime(2024, 1, 1, 0, 0, 0)
        wf.approved_by = "old-reviewer"
        session.commit()

    stale_context = WorkflowContext(campaign_topic="approval invalidation", platforms=["Instagram"])
    stale_context.approval_status = "APPROVED"
    stale_context.approval_content_hash = valid_hash
    stale_context.approved_by = "stale-reviewer"
    stale_context.approval_notes = "stale note"

    manager.save_workflow_checkpoint(workflow.id, stale_context, agent_name="Trend Research Agent", status="RUNNING")

    persisted = manager.get_workflow(workflow.id)
    assert persisted is not None
    assert persisted.approval_status == "APPROVED"
    assert persisted.approval_content_hash is None
    assert persisted.approved_at is not None

    manager.record_approval_decision(workflow.id, "REQUESTED_CHANGES", approved_by="new-reviewer", notes="Revise this.", content_hash="old-hash")
    after_request = manager.get_workflow(workflow.id)
    assert after_request is not None
    assert after_request.approval_status == "REQUESTED_CHANGES"
    assert after_request.approval_content_hash is None
    assert after_request.approved_at is None

    manager.record_approval_decision(workflow.id, "REJECTED", approved_by="new-reviewer", notes="Rejected.", content_hash="new-hash")
    after_reject = manager.get_workflow(workflow.id)
    assert after_reject is not None
    assert after_reject.approval_status == "REJECTED"
    assert after_reject.approval_content_hash is None
    assert after_reject.approved_at is None

    manager.record_approval_decision(workflow.id, "PENDING", approved_by="new-reviewer", notes="Pending review.", content_hash="later-hash")
    after_pending = manager.get_workflow(workflow.id)
    assert after_pending is not None
    assert after_pending.approval_status == "PENDING"
    assert after_pending.approval_content_hash is None
    assert after_pending.approved_at is None
