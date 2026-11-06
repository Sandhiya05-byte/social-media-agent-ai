from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from app.config import DEFAULT_WORKFLOW_RETRY_LIMIT
from app.orchestration.agent_registry import AgentRegistry
from app.orchestration.execution_manager import ExecutionManager
from app.orchestration.workflow_context import WorkflowContext
from app.time_utils import utcnow


class WorkflowEngine:
    def __init__(self, registry: AgentRegistry | None = None, execution_manager: ExecutionManager | None = None):
        self.registry = registry or AgentRegistry()
        self.execution_manager = execution_manager or ExecutionManager()

    @staticmethod
    def _status_key(value: str | None) -> str:
        return str(value or "").upper()

    @staticmethod
    def _content_fingerprint(context: WorkflowContext) -> str:
        payload = {
            "campaign_topic": context.campaign_topic,
            "target_audience": context.target_audience,
            "platforms": context.platforms,
            "campaign_objective": context.campaign_objective,
            "content_type": context.content_type,
            "brand_voice": context.brand_voice,
            "research_findings": context.research_findings,
            "competitor_findings": context.competitor_findings,
            "hooks": context.hooks,
            "creative_output": context.creative_output,
            "video_output": context.video_output,
            "validation_result": context.validation_result,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()

    def _enforce_approval_gate(
        self,
        workflow_id: int,
        context: WorkflowContext,
        *,
        action: str,
        session=None,
    ) -> None:
        workflow = self.execution_manager.get_workflow(workflow_id, session=session)
        if workflow is None:
            raise RuntimeError(f"Workflow {workflow_id} was not found; human approval cannot be bypassed.")

        approval_status = self._status_key(workflow.approval_status)
        if approval_status != "APPROVED":
            raise RuntimeError(f"Human approval is required before {action}.")

        persisted_hash = workflow.approval_content_hash or ""
        if not persisted_hash:
            raise RuntimeError("Workflow approval is missing a persisted content fingerprint.")

        current_hash = self._content_fingerprint(context)
        if persisted_hash != current_hash:
            raise RuntimeError("Content was changed after approval; a fresh human approval is required.")

        restored_context_hash = context.approval_content_hash or ""
        if not restored_context_hash or restored_context_hash != persisted_hash:
            raise RuntimeError("Workflow approval does not match the current content version.")

    def _block_before_scheduling(
        self,
        workflow_id: int,
        context: WorkflowContext,
        *,
        agent_name: str,
        session=None,
    ) -> bool:
        if agent_name != "Publishing and Scheduling Agent":
            return False

        workflow = self.execution_manager.get_workflow(workflow_id, session=session)
        if workflow is None:
            raise RuntimeError(f"Workflow {workflow_id} was not found; human approval cannot be bypassed.")

        db_approval_status = self._status_key(workflow.approval_status)
        if db_approval_status in {"", "PENDING", "WAITING_FOR_APPROVAL", "REQUESTED_CHANGES"}:
            context.approval_status = "PENDING"
            context.error_message = "Human approval is required before scheduling."
            summary = {
                "failed_agent": agent_name,
                "status": "waiting_for_approval",
                "requires_human_approval": True,
            }
            self.execution_manager.save_workflow_checkpoint(
                workflow_id,
                context,
                agent_name="WAITING_FOR_APPROVAL",
                status="WAITING_FOR_APPROVAL",
                execution_summary=summary,
                session=session,
            )
            self.execution_manager.update_workflow(
                workflow_id,
                "WAITING_FOR_APPROVAL",
                error_message=context.error_message,
                execution_summary=summary,
                session=session,
            )
            # P0 auto-bridge: agents 1-6 completed, so the generated content
            # must reach the approval queue even though agent 7 is gated.
            try:
                self.execution_manager.create_content_item_from_workflow(workflow_id, session=session)
            except Exception as exc:  # noqa: BLE001 - bridge failure must not fail the run
                summary = {**summary, "content_bridge_failed": str(exc)}
                self.execution_manager.update_workflow(
                    workflow_id,
                    "WAITING_FOR_APPROVAL",
                    error_message=f"Content bridge failed: {exc}",
                    execution_summary=summary,
                    session=session,
                )
            return True

        self._enforce_approval_gate(workflow_id, context, action="scheduling", session=session)
        return False

    def _build_agent_inputs(self, agent_name: str, context: WorkflowContext) -> dict[str, Any]:
        if agent_name == "Trend Research Agent":
            return {
                "niche": context.campaign_topic,
                "source_urls": context.research_findings.get("rss_sources", []) if isinstance(context.research_findings, dict) else [],
            }
        if agent_name == "Competitor Intelligence Agent":
            competitor_urls = context.competitor_findings.get("competitor_urls", []) if isinstance(context.competitor_findings, dict) else []
            return {
                "niche": context.campaign_topic,
                "competitor_urls": competitor_urls,
                "research_results": context.research_findings,
            }
        if agent_name == "Brand Voice Agent":
            samples = context.brand_voice.get("samples", []) if isinstance(context.brand_voice, dict) else []
            return {
                "niche": context.campaign_topic,
                "creator_samples": samples,
                "target_audience": context.target_audience,
                "campaign_objective": context.campaign_objective,
                "research_results": context.research_findings,
            }
        if agent_name == "Hook Generation Agent":
            voice_profile = context.brand_voice.get("voice_profile", {}) if isinstance(context.brand_voice, dict) else {}
            return {
                "niche": context.campaign_topic,
                "creator_style": voice_profile,
                "target_audience": context.target_audience,
                "research_results": context.research_findings,
                "competitor_findings": context.competitor_findings,
            }
        if agent_name == "AI Clone and Creative Agent":
            return {
                "campaign_topic": context.campaign_topic,
                "target_audience": context.target_audience,
                "campaign_objective": context.campaign_objective,
                "content_type": context.content_type,
                "brand_voice": context.brand_voice,
                "research_findings": context.research_findings,
                "competitor_findings": context.competitor_findings,
                "hooks": context.hooks,
                "recommended_hook": context.recommended_hook,
                "platform": context.platforms[0] if context.platforms else "Instagram",
            }
        if agent_name == "Video Production Agent":
            creative = context.creative_output
            return {
                "title": creative.get("title") or f"{context.campaign_topic} short-form video",
                "script": creative.get("script") or (context.hooks[0] if context.hooks else context.campaign_topic),
                "platform": context.platforms[0] if context.platforms else "Instagram",
                "captions": creative.get("captions", []),
                "content": creative.get("content", ""),
            }
        if agent_name == "Publishing and Scheduling Agent":
            return {
                "campaign_topic": context.campaign_topic,
                "platforms": context.platforms,
                "status": context.approval_status,
                "creative_output": {
                    "title": context.creative_output.get("title", ""),
                    "content": context.creative_output.get("content", ""),
                    "script": context.creative_output.get("script"),
                    "captions": context.creative_output.get("captions", []),
                },
            }
        return {}

    @staticmethod
    def _apply_agent_result(agent_name: str, result: dict[str, Any], context: WorkflowContext) -> None:
        context.agent_records[agent_name] = result
        if agent_name == "Trend Research Agent":
            context.research_findings = {
                "topic_summary": result.get("topic_summary"),
                "ranked_topic_suggestions": result.get("trending_subtopics", []),
                "rss_sources": result.get("rss_sources", []),
                "source_references": result.get("source_references", []),
                "keywords": result.get("keywords", []),
                "observations": result.get("observations", []),
                "provider_statuses": result.get("provider_statuses", {}),
                "provider_limitations": result.get("provider_limitations", []),
                "research_status": result.get("research_status"),
            }
        elif agent_name == "Competitor Intelligence Agent":
            context.competitor_findings = {
                "observations": result.get("observations", []),
                "competitor_urls": result.get("competitor_urls", []),
                "user_supplied_urls": result.get("user_supplied_urls", []),
                "source_references": result.get("source_references", []),
            }
        elif agent_name == "Brand Voice Agent":
            context.brand_voice = {
                "samples": result.get("creator_samples", []),
                "voice_profile": result.get("voice_profile", {}),
                "summary": result.get("summary"),
            }
        elif agent_name == "Hook Generation Agent":
            context.hooks = result.get("hook_alternatives", [])
            context.recommended_hook = result.get("recommended_hook")
        elif agent_name == "AI Clone and Creative Agent":
            context.creative_output = {
                "title": result.get("title"),
                "content": result.get("content"),
                "script": result.get("script"),
                "captions": result.get("captions", []),
                "hashtags": result.get("hashtags", []),
                "generation_source": result.get("generation_source"),
                "summary": result.get("summary"),
                "generated_file": result.get("generated_file"),
                "preview_url": result.get("preview_url"),
                "platform": result.get("platform"),
            }
        elif agent_name == "Video Production Agent":
            context.video_output = {
                "platform": result.get("platform"),
                "video_path": result.get("video_path"),
                "video_format": result.get("video_format"),
                "render_engine": result.get("render_engine"),
                "thumbnail_path": result.get("thumbnail_path"),
                "subtitle_path": result.get("subtitle_path"),
                "captions": result.get("captions", []),
                # Full media metadata so the frontend can render the actual
                # MP4 with sound instead of a stale GIF preview.
                "video_url": result.get("video_url"),
                "thumbnail_url": result.get("thumbnail_url"),
                "subtitle_url": result.get("subtitle_url"),
                "narration_audio_path": result.get("narration_audio_path"),
                "duration_seconds": result.get("duration_seconds"),
                "video_width": result.get("video_width"),
                "video_height": result.get("video_height"),
                "audio_enabled": result.get("audio_enabled"),
                "scene_count": result.get("scene_count"),
                "script_sufficient": result.get("script_sufficient"),
                "render_error": result.get("render_error"),
                "tts_error": result.get("tts_error"),
                "limits": result.get("limits"),
            }
            try:
                from app.services.content_validation import validate_content_payload

                validation = validate_content_payload(
                    {
                        "title": context.creative_output.get("title") or context.campaign_topic,
                        "platform": context.platforms[0] if context.platforms else "Instagram",
                        "content": context.creative_output.get("content") or "",
                        "script": context.creative_output.get("script"),
                        "captions": context.creative_output.get("captions", []),
                        "media_path": result.get("video_path"),
                    }
                )
                context.validation_result = validation.model_dump()
            except Exception:
                context.validation_result = {}
        elif agent_name == "Publishing and Scheduling Agent":
            context.scheduling = result.get("schedule", {})

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
            approval_status=workflow.approval_status or (workflow.status if workflow.status in {"APPROVED", "REJECTED", "SCHEDULED", "COMPLETED", "WAITING_FOR_APPROVAL"} else "PENDING"),
            approval_content_hash=workflow.approval_content_hash,
            approval_notes=workflow.approval_notes,
            approved_by=workflow.approved_by,
            content_version=workflow.content_version,
        )

    def run(self, context: WorkflowContext) -> WorkflowContext:
        self.registry.register_default_agents()
        workflow = self.execution_manager.create_workflow(context)
        self.execution_manager.update_workflow(workflow.id, "RUNNING", execution_summary={"status": "running"})
        context.workflow_id = workflow.id
        context.agent_records = {}

        for agent_name in self.registry.execution_order():
            if self._block_before_scheduling(workflow.id, context, agent_name=agent_name):
                return context

            started_at = utcnow()
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
                completed_at = utcnow()
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

            completed_at = utcnow()
            result_status = str(result.get("status", "completed")).upper()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            self._apply_agent_result(agent_name, result, context)

            try:
                self.execution_manager.save_workflow_checkpoint(workflow.id, context, agent_name=agent_name)
            except Exception as exc:
                checkpoint_error = f"Checkpoint persistence failed after successful agent '{agent_name}': {exc}"
                self.execution_manager.update_agent_execution(
                    execution_record.id,
                    status="FAILED",
                    output_data={"error": checkpoint_error, "result": result},
                    completed_at=utcnow(),
                    execution_duration=int((utcnow() - started_at).total_seconds() * 1000),
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
        context.approval_content_hash = self._content_fingerprint(context)
        context.content_version = int(context.content_version or 1)
        final_summary = {
            "agent_count": len(context.agent_records),
            "campaign_topic": context.campaign_topic,
            "platforms": context.platforms,
            "status": "waiting_for_approval",
        }

        try:
            self.execution_manager.save_workflow_checkpoint(
                workflow.id,
                context,
                agent_name="COMPLETED",
                status="WAITING_FOR_APPROVAL",
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

        self.execution_manager.update_workflow(
            workflow.id,
            "WAITING_FOR_APPROVAL",
            error_message=None,
            execution_summary=final_summary,
        )

        # P0 auto-bridge: a completed workflow always has its ContentItem.
        try:
            self.execution_manager.create_content_item_from_workflow(workflow.id)
        except Exception as exc:  # noqa: BLE001 - bridge failure must not fail the run
            context.error_message = f"Content bridge failed: {exc}"
            self.execution_manager.update_workflow(
                workflow.id,
                "WAITING_FOR_APPROVAL",
                error_message=context.error_message,
                execution_summary={**final_summary, "content_bridge_failed": str(exc)},
            )
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
            if workflow_status not in {"FAILED", "CREATED", "WAITING_FOR_APPROVAL", "APPROVED"}:
                raise RuntimeError(f"Workflow status '{workflow.status}' is not eligible for retry.")

            context = self._restore_context_for_workflow(workflow_id)
            if workflow_status in {"WAITING_FOR_APPROVAL", "APPROVED"}:
                try:
                    self._enforce_approval_gate(workflow_id, context, action="resume")
                except RuntimeError:
                    if workflow_status == "WAITING_FOR_APPROVAL":
                        raise RuntimeError("Workflow is waiting for human approval before it can resume.")
                    raise

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
                if self._block_before_scheduling(
                    workflow_id,
                    context,
                    agent_name=agent_name,
                    session=session,
                ):
                    return context
                started_at = utcnow()
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
                    completed_at = utcnow()
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

                completed_at = utcnow()
                duration_ms = int((completed_at - started_at).total_seconds() * 1000)
                result_status = str(result.get("status", "completed")).upper()

                self._apply_agent_result(agent_name, result, context)

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
                        completed_at=utcnow(),
                        execution_duration=int((utcnow() - started_at).total_seconds() * 1000),
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
