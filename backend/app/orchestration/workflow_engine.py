from __future__ import annotations

from datetime import datetime
from typing import Any

from app.config import DEFAULT_WORKFLOW_RETRY_LIMIT
from app.orchestration.agent_registry import AgentRegistry
from app.orchestration.execution_manager import ExecutionManager
from app.orchestration.workflow_context import WorkflowContext


class WorkflowEngine:
    def __init__(self, registry: AgentRegistry | None = None, execution_manager: ExecutionManager | None = None):
        self.registry = registry or AgentRegistry()
        self.execution_manager = execution_manager or ExecutionManager()

    @staticmethod
    def _status_key(value: str | None) -> str:
        return str(value or "").upper()

    def _build_agent_inputs(self, agent_name: str, context: WorkflowContext) -> dict[str, Any]:
        if agent_name == "Trend Research Agent":
            return {
                "niche": context.campaign_topic,
                "source_urls": context.research_findings.get("rss_sources", []) if isinstance(context.research_findings, dict) else [],
            }
        if agent_name == "Competitor Intelligence Agent":
            competitor_urls = context.competitor_findings.get("competitor_urls", []) if isinstance(context.competitor_findings, dict) else []
            return {"niche": context.campaign_topic, "competitor_urls": competitor_urls}
        if agent_name == "Brand Voice Agent":
            samples = context.brand_voice.get("samples", []) if isinstance(context.brand_voice, dict) else []
            return {"niche": context.campaign_topic, "creator_samples": samples}
        if agent_name == "Hook Generation Agent":
            voice_profile = context.brand_voice.get("voice_profile", {}) if isinstance(context.brand_voice, dict) else {}
            return {"niche": context.campaign_topic, "creator_style": voice_profile}
        if agent_name == "AI Clone and Creative Agent":
            return {
                "title": f"{context.campaign_topic} creative direction",
                "platform": context.platforms[0] if context.platforms else "Instagram",
                "content": context.campaign_objective,
            }
        if agent_name == "Video Production Agent":
            return {
                "title": f"{context.campaign_topic} short-form video",
                "script": context.hooks[0] if context.hooks else context.campaign_topic,
                "platform": context.platforms[0] if context.platforms else "Instagram",
            }
        if agent_name == "Publishing and Scheduling Agent":
            return {
                "campaign_topic": context.campaign_topic,
                "platforms": context.platforms,
                "status": context.approval_status,
            }
        return {}

    def _restore_context_for_workflow(self, workflow_id: int) -> WorkflowContext:
        context = self.execution_manager.get_workflow_context(workflow_id)
        if context is not None:
            return context

        workflow = self.execution_manager.get_workflow(workflow_id)
        if workflow is None:
            raise ValueError(f"Workflow {workflow_id} was not found.")
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

    def run(self, context: WorkflowContext) -> WorkflowContext:
        self.registry.register_default_agents()
        workflow = self.execution_manager.create_workflow(context)
        self.execution_manager.update_workflow(workflow.id, "RUNNING", execution_summary={"status": "running"})
        context.workflow_id = workflow.id
        context.agent_records = {}

        for agent_name in self.registry.execution_order():
            started_at = datetime.utcnow()
            input_data = self._build_agent_inputs(agent_name, context)
            execution_record = self.execution_manager.add_agent_execution(
                workflow_id=workflow.id,
                agent_name=agent_name,
                status="RUNNING",
                input_data=input_data,
                started_at=started_at,
            )

            try:
                agent = self.registry.get(agent_name)
                result = agent.execute(**input_data)
            except Exception as exc:  # pragma: no cover - defensive guard
                completed_at = datetime.utcnow()
                self.execution_manager.update_agent_execution(
                    execution_record.id,
                    status="FAILED",
                    output_data={"error": str(exc)},
                    completed_at=completed_at,
                    execution_duration=int((completed_at - started_at).total_seconds() * 1000),
                    error_message=str(exc),
                )
                context.error_message = str(exc)
                self.execution_manager.update_workflow(
                    workflow.id,
                    "FAILED",
                    error_message=str(exc),
                    execution_summary={"failed_agent": agent_name},
                )
                return context

            completed_at = datetime.utcnow()
            result_status = str(result.get("status", "completed")).upper()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            context.agent_records[agent_name] = result
            if agent_name == "Trend Research Agent":
                context.research_findings = {"ranked_topic_suggestions": result.get("ranked_topic_suggestions", []), "rss_sources": result.get("source_urls", [])}
            elif agent_name == "Competitor Intelligence Agent":
                context.competitor_findings = {"observations": result.get("observations", []), "competitor_urls": result.get("competitor_urls", [])}
            elif agent_name == "Brand Voice Agent":
                context.brand_voice = {
                    "samples": result.get("creator_samples", []),
                    "voice_profile": result.get("voice_profile", {}),
                }
            elif agent_name == "Hook Generation Agent":
                context.hooks = result.get("hook_alternatives", [])
            elif agent_name == "AI Clone and Creative Agent":
                context.creative_output = {
                    "platform": result.get("platform"),
                    "generated_file": result.get("generated_file"),
                    "preview_url": result.get("preview_url"),
                }
            elif agent_name == "Video Production Agent":
                context.video_output = {
                    "platform": result.get("platform"),
                    "video_path": result.get("video_path"),
                    "thumbnail_path": result.get("thumbnail_path"),
                    "subtitle_path": result.get("subtitle_path"),
                }

            try:
                self.execution_manager.save_workflow_checkpoint(workflow.id, context, agent_name=agent_name)
            except Exception as exc:
                checkpoint_error = f"Checkpoint persistence failed after successful agent '{agent_name}': {exc}"
                self.execution_manager.update_agent_execution(
                    execution_record.id,
                    status="FAILED",
                    output_data={"error": checkpoint_error, "result": result},
                    completed_at=datetime.utcnow(),
                    execution_duration=int((datetime.utcnow() - started_at).total_seconds() * 1000),
                    error_message=checkpoint_error,
                )
                context.error_message = checkpoint_error
                self.execution_manager.update_workflow(
                    workflow.id,
                    "FAILED",
                    error_message=checkpoint_error,
                    execution_summary={"failed_agent": agent_name, "checkpoint_failed": True},
                )
                raise

            self.execution_manager.update_agent_execution(
                execution_record.id,
                status=result_status,
                output_data=result,
                completed_at=completed_at,
                execution_duration=duration_ms,
            )

        context.approval_status = "PENDING"
        final_summary = {
            "agent_count": len(context.agent_records),
            "campaign_topic": context.campaign_topic,
            "platforms": context.platforms,
            "status": "completed",
        }

        try:
            self.execution_manager.save_workflow_checkpoint(
                workflow.id,
                context,
                agent_name="COMPLETED",
                status="COMPLETED",
                execution_summary=final_summary,
            )
        except Exception as exc:
            checkpoint_error = f"Final checkpoint persistence failed for workflow {workflow.id}: {exc}"
            context.error_message = checkpoint_error
            self.execution_manager.update_workflow(
                workflow.id,
                "FAILED",
                error_message=checkpoint_error,
                execution_summary={"failed_agent": "workflow_completion", "checkpoint_failed": True},
            )
            raise

        return context

    def resume_workflow(self, workflow_id: int, retry_limit: int | None = None) -> WorkflowContext:
        retry_limit = retry_limit if retry_limit is not None else DEFAULT_WORKFLOW_RETRY_LIMIT
        with self.execution_manager.workflow_retry_lock(workflow_id) as (workflow, session):
            if workflow is None:
                raise ValueError(f"Workflow {workflow_id} was not found.")

            workflow_status = self._status_key(workflow.status)
            if workflow_status == "RUNNING":
                raise RuntimeError("Workflow is already RUNNING and cannot be retried.")
            if workflow_status in {"COMPLETED", "CANCELLED", "REJECTED", "SCHEDULED"}:
                raise RuntimeError(f"Workflow status '{workflow.status}' is not eligible for retry.")
            if workflow_status not in {"FAILED", "CREATED"}:
                raise RuntimeError(f"Workflow status '{workflow.status}' is not eligible for retry.")

            context = self._restore_context_for_workflow(workflow_id)
            self.registry.register_default_agents()
            execution_rows = self.execution_manager.list_agent_executions(workflow_id, session=session)
            execution_by_name = {row.agent_name: row for row in execution_rows}
            ordered_agents = self.registry.execution_order()

            resume_from_index = None
            for index, agent_name in enumerate(ordered_agents):
                current_status = self._status_key(execution_by_name.get(agent_name).status if execution_by_name.get(agent_name) else "PENDING")
                if current_status == "COMPLETED":
                    continue

                missing_upstream = False
                prior_name = None
                for prior_name in ordered_agents[:index]:
                    prior_record = execution_by_name.get(prior_name)
                    prior_status = self._status_key(prior_record.status if prior_record else "PENDING")
                    if prior_status != "COMPLETED":
                        missing_upstream = True
                        break

                if missing_upstream:
                    raise RuntimeError(f"Dependency error: upstream agent '{prior_name}' has not completed for '{agent_name}'.")

                resume_from_index = index
                break

            if resume_from_index is None:
                self.execution_manager.update_workflow(workflow_id, "RUNNING", error_message=None, execution_summary={"status": "already_complete"})
                return context

            self.execution_manager.update_workflow(
                workflow_id,
                "RUNNING",
                error_message=None,
                execution_summary={"resuming_from_agent": ordered_agents[resume_from_index]},
                session=session,
            )

            for index in range(resume_from_index, len(ordered_agents)):
                agent_name = ordered_agents[index]
                started_at = datetime.utcnow()
                input_data = self._build_agent_inputs(agent_name, context)
                latest_execution = self.execution_manager.get_agent_execution(workflow_id, agent_name, session=session)
                retry_count = 0
                if latest_execution is not None and self._status_key(latest_execution.status) == "FAILED":
                    retry_count = int(latest_execution.retry_count or 0) + 1
                    if retry_count > retry_limit:
                        raise RuntimeError(f"Retry limit of {retry_limit} reached for '{agent_name}'.")
                    self.execution_manager.update_agent_execution(
                        latest_execution.id,
                        status="RUNNING",
                        input_data=input_data,
                        output_data={},
                        started_at=started_at,
                        completed_at=None,
                        execution_duration=0,
                        retry_count=retry_count,
                        error_message=None,
                        session=session,
                    )
                    execution_record = latest_execution
                else:
                    if latest_execution is not None and self._status_key(latest_execution.status) == "COMPLETED":
                        continue
                    execution_record = self.execution_manager.add_agent_execution(
                        workflow_id=workflow_id,
                        agent_name=agent_name,
                        status="RUNNING",
                        input_data=input_data,
                        started_at=started_at,
                        session=session,
                    )

                try:
                    agent = self.registry.get(agent_name)
                    result = agent.execute(**input_data)
                except Exception as exc:  # pragma: no cover - defensive guard
                    completed_at = datetime.utcnow()
                    self.execution_manager.update_agent_execution(
                        execution_record.id,
                        status="FAILED",
                        input_data=input_data,
                        output_data={"error": str(exc)},
                        started_at=started_at,
                        completed_at=completed_at,
                        execution_duration=int((completed_at - started_at).total_seconds() * 1000),
                        retry_count=retry_count if retry_count else int(getattr(execution_record, "retry_count", 0) or 0),
                        error_message=str(exc),
                        session=session,
                    )
                    self.execution_manager.update_workflow(
                        workflow_id,
                        "FAILED",
                        error_message=str(exc),
                        execution_summary={"failed_agent": agent_name, "retry_count": retry_count or 0},
                        session=session,
                    )
                    return context

                completed_at = datetime.utcnow()
                duration_ms = int((completed_at - started_at).total_seconds() * 1000)
                result_status = str(result.get("status", "completed")).upper()

                context.agent_records[agent_name] = result
                if agent_name == "Trend Research Agent":
                    context.research_findings = {"ranked_topic_suggestions": result.get("ranked_topic_suggestions", []), "rss_sources": result.get("source_urls", [])}
                elif agent_name == "Competitor Intelligence Agent":
                    context.competitor_findings = {"observations": result.get("observations", []), "competitor_urls": result.get("competitor_urls", [])}
                elif agent_name == "Brand Voice Agent":
                    context.brand_voice = {"samples": result.get("creator_samples", []), "voice_profile": result.get("voice_profile", {})}
                elif agent_name == "Hook Generation Agent":
                    context.hooks = result.get("hook_alternatives", [])
                elif agent_name == "AI Clone and Creative Agent":
                    context.creative_output = {"platform": result.get("platform"), "generated_file": result.get("generated_file"), "preview_url": result.get("preview_url")}
                elif agent_name == "Video Production Agent":
                    context.video_output = {"platform": result.get("platform"), "video_path": result.get("video_path"), "thumbnail_path": result.get("thumbnail_path"), "subtitle_path": result.get("subtitle_path")}

                try:
                    self.execution_manager.save_workflow_checkpoint(workflow_id, context, agent_name=agent_name, session=session)
                except Exception as exc:
                    checkpoint_error = f"Checkpoint persistence failed after successful agent '{agent_name}': {exc}"
                    self.execution_manager.update_agent_execution(
                        execution_record.id,
                        status="FAILED",
                        input_data=input_data,
                        output_data={"error": checkpoint_error, "result": result},
                        started_at=started_at,
                        completed_at=datetime.utcnow(),
                        execution_duration=int((datetime.utcnow() - started_at).total_seconds() * 1000),
                        retry_count=retry_count if retry_count else int(getattr(execution_record, "retry_count", 0) or 0),
                        error_message=checkpoint_error,
                        session=session,
                    )
                    self.execution_manager.update_workflow(
                        workflow_id,
                        "FAILED",
                        error_message=checkpoint_error,
                        execution_summary={"failed_agent": agent_name, "checkpoint_failed": True},
                        session=session,
                    )
                    raise

                self.execution_manager.update_agent_execution(
                    execution_record.id,
                    status=result_status,
                    input_data=input_data,
                    output_data=result,
                    started_at=started_at,
                    completed_at=completed_at,
                    execution_duration=duration_ms,
                    retry_count=retry_count if retry_count else int(getattr(execution_record, "retry_count", 0) or 0),
                    session=session,
                )

            final_summary = {
                "agent_count": len(context.agent_records),
                "campaign_topic": context.campaign_topic,
                "platforms": context.platforms,
                "status": "completed",
            }

            try:
                self.execution_manager.save_workflow_checkpoint(
                    workflow_id,
                    context,
                    agent_name="COMPLETED",
                    status="COMPLETED",
                    execution_summary=final_summary,
                    session=session,
                )
            except Exception as exc:
                checkpoint_error = f"Final checkpoint persistence failed for workflow {workflow_id}: {exc}"
                self.execution_manager.update_workflow(
                    workflow_id,
                    "FAILED",
                    error_message=checkpoint_error,
                    execution_summary={"failed_agent": "workflow_completion", "checkpoint_failed": True},
                    session=session,
                )
                raise

            return context
