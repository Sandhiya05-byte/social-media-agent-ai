from __future__ import annotations

from datetime import datetime
from typing import Any

from app.database import SessionLocal, init_db
from app.models.workflow import AgentExecution, Workflow
from app.orchestration.workflow_context import WorkflowContext


class ExecutionManager:
    def __init__(self, session_factory=SessionLocal):
        init_db()
        self.session_factory = session_factory

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): ExecutionManager._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [ExecutionManager._json_safe(item) for item in value]
        return str(value)

    def create_workflow(self, context) -> Workflow:
        with self.session_factory() as session:
            workflow = Workflow(
                creator_id=context.creator_id,
                campaign_topic=context.campaign_topic,
                target_audience=context.target_audience,
                platforms=context.platforms,
                campaign_objective=context.campaign_objective,
                content_type=context.content_type,
                status="CREATED",
                execution_summary={},
                checkpoint_data={},
            )
            session.add(workflow)
            session.commit()
            session.refresh(workflow)
            context.workflow_id = workflow.id
            return workflow

    def update_workflow(
        self,
        workflow_id: int,
        status: str,
        error_message: str | None = None,
        execution_summary: dict[str, Any] | None = None,
        checkpoint_data: dict[str, Any] | None = None,
    ) -> None:
        with self.session_factory() as session:
            workflow = session.get(Workflow, workflow_id)
            if workflow is None:
                return
            workflow.status = status
            workflow.error_message = error_message
            workflow.execution_summary = execution_summary or workflow.execution_summary
            if checkpoint_data is not None:
                workflow.checkpoint_data = self._json_safe(checkpoint_data)
            workflow.updated_at = datetime.utcnow()
            if status in {"COMPLETED", "FAILED", "CANCELLED"}:
                workflow.completed_at = datetime.utcnow()
            session.commit()

    def save_workflow_checkpoint(
        self,
        workflow_id: int,
        context: WorkflowContext,
        agent_name: str | None = None,
        status: str | None = None,
        error_message: str | None = None,
        execution_summary: dict[str, Any] | None = None,
    ) -> Workflow | None:
        with self.session_factory() as session:
            workflow = session.get(Workflow, workflow_id)
            if workflow is None:
                return None

            payload = self._json_safe(context.to_dict())
            workflow.checkpoint_data = payload
            workflow.last_successful_agent = agent_name or workflow.last_successful_agent
            workflow.last_checkpoint_at = datetime.utcnow()
            workflow.updated_at = datetime.utcnow()
            if status is not None:
                workflow.status = status
                workflow.error_message = error_message
                workflow.execution_summary = self._json_safe(execution_summary or workflow.execution_summary)
                if status in {"COMPLETED", "FAILED", "CANCELLED"}:
                    workflow.completed_at = datetime.utcnow()
            elif error_message is not None:
                workflow.error_message = error_message
            if execution_summary is not None and status is None:
                workflow.execution_summary = self._json_safe(execution_summary)
            session.commit()
            session.refresh(workflow)
            return workflow

    def get_workflow_context(self, workflow_id: int) -> WorkflowContext | None:
        with self.session_factory() as session:
            workflow = session.get(Workflow, workflow_id)
            if workflow is None:
                return None
            if workflow.checkpoint_data:
                return WorkflowContext.from_dict(workflow.checkpoint_data)
            return WorkflowContext(
                workflow_id=workflow.id,
                creator_id=workflow.creator_id,
                campaign_topic=workflow.campaign_topic,
                target_audience=workflow.target_audience,
                platforms=list(workflow.platforms or []),
                campaign_objective=workflow.campaign_objective,
                content_type=workflow.content_type,
                approval_status=workflow.status if workflow.status in {"APPROVED", "REJECTED", "SCHEDULED", "COMPLETED"} else "PENDING",
            )

    def add_agent_execution(self, workflow_id: int, agent_name: str, status: str, input_data: dict[str, Any], output_data: dict[str, Any] | None = None, started_at: datetime | None = None, completed_at: datetime | None = None, execution_duration: int = 0, error_message: str | None = None) -> AgentExecution:
        with self.session_factory() as session:
            record = AgentExecution(
                workflow_id=workflow_id,
                agent_name=agent_name,
                status=status,
                input_data=input_data,
                output_data=output_data or {},
                started_at=started_at,
                completed_at=completed_at,
                execution_duration=execution_duration,
                error_message=error_message,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def update_agent_execution(
        self,
        execution_id: int,
        *,
        status: str | None = None,
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        execution_duration: int | None = None,
        error_message: str | None = None,
    ) -> AgentExecution | None:
        with self.session_factory() as session:
            record = session.get(AgentExecution, execution_id)
            if record is None:
                return None
            if status is not None:
                record.status = status
            if input_data is not None:
                record.input_data = self._json_safe(input_data)
            if output_data is not None:
                record.output_data = self._json_safe(output_data)
            if started_at is not None:
                record.started_at = started_at
            if completed_at is not None:
                record.completed_at = completed_at
            if execution_duration is not None:
                record.execution_duration = execution_duration
            if error_message is not None:
                record.error_message = error_message
            session.commit()
            session.refresh(record)
            return record

    def get_agent_execution(self, workflow_id: int, agent_name: str) -> AgentExecution | None:
        with self.session_factory() as session:
            return (
                session.query(AgentExecution)
                .filter(AgentExecution.workflow_id == workflow_id, AgentExecution.agent_name == agent_name)
                .order_by(AgentExecution.id.desc())
                .first()
            )

    def get_workflow(self, workflow_id: int) -> Workflow | None:
        with self.session_factory() as session:
            return session.get(Workflow, workflow_id)
