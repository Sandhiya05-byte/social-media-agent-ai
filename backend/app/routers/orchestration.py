from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.orchestration.orchestrator import CentralAgentOrchestrator
from app.orchestration.workflow_engine import WorkflowEngine

router = APIRouter(prefix="/api/orchestration", tags=["orchestration"])


class WorkflowRequest(BaseModel):
    creator_id: int | None = None
    campaign_topic: str = Field(..., min_length=1)
    target_audience: str = "general audience"
    platforms: list[str] = ["Instagram", "YouTube"]
    campaign_objective: str = "content growth"
    content_type: str = "short-form"
    competitor_urls: list[str] = []
    rss_sources: list[str] = []
    creator_writing_samples: list[str] = []
    brand_voice: dict = {}


class WorkflowApprovalRequest(BaseModel):
    approved_by: str | None = None
    notes: str | None = None


@router.post("/workflows")
def create_and_run_workflow(payload: WorkflowRequest):
    orchestrator = CentralAgentOrchestrator()
    try:
        context = orchestrator.run(
            creator_id=payload.creator_id,
            campaign_topic=payload.campaign_topic,
            target_audience=payload.target_audience,
            platforms=payload.platforms,
            campaign_objective=payload.campaign_objective,
            content_type=payload.content_type,
            competitor_urls=payload.competitor_urls,
            rss_sources=payload.rss_sources,
            creator_writing_samples=payload.creator_writing_samples,
            brand_voice=payload.brand_voice,
        )
    except Exception as exc:  # pragma: no cover - network failure wrapper
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"workflow_id": context.workflow_id, "status": context.approval_status if context.approval_status else "WAITING_FOR_APPROVAL", "context": context.to_dict()}


@router.post("/workflows/{workflow_id}/approve")
def approve_workflow(workflow_id: int, payload: WorkflowApprovalRequest):
    from app.orchestration.execution_manager import ExecutionManager

    manager = ExecutionManager()
    workflow = manager.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    if workflow.status not in {"WAITING_FOR_APPROVAL", "PENDING", "APPROVED"}:
        raise HTTPException(status_code=409, detail="Workflow is not awaiting approval.")

    context = manager.get_workflow_context(workflow_id)
    if context is None:
        raise HTTPException(status_code=404, detail="Workflow checkpoint not found.")

    approved_by = payload.approved_by or "human-reviewer"
    notes = payload.notes
    current_content_hash = WorkflowEngine()._content_fingerprint(context)
    context.approval_status = "APPROVED"
    context.approved_by = approved_by
    context.approval_notes = notes
    context.approval_content_hash = current_content_hash
    manager.record_approval_decision(
        workflow_id,
        "APPROVED",
        approved_by=approved_by,
        notes=notes,
        content_hash=current_content_hash,
    )
    manager.save_workflow_checkpoint(workflow_id, context, agent_name="COMPLETED", status="APPROVED", execution_summary={"status": "approved"})
    return {"workflow_id": workflow_id, "status": "APPROVED", "context": context.to_dict()}


@router.post("/workflows/{workflow_id}/reject")
def reject_workflow(workflow_id: int, payload: WorkflowApprovalRequest):
    from app.orchestration.execution_manager import ExecutionManager

    manager = ExecutionManager()
    workflow = manager.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    if workflow.status not in {"WAITING_FOR_APPROVAL", "PENDING", "APPROVED"}:
        raise HTTPException(status_code=409, detail="Workflow is not awaiting approval.")

    context = manager.get_workflow_context(workflow_id)
    if context is None:
        raise HTTPException(status_code=404, detail="Workflow checkpoint not found.")

    context.approval_status = "REJECTED"
    context.approval_notes = payload.notes or "Rejected by human reviewer."
    context.approved_by = payload.approved_by or "human-reviewer"
    manager.record_approval_decision(
        workflow_id,
        "REJECTED",
        approved_by=context.approved_by,
        notes=context.approval_notes,
        content_hash=context.approval_content_hash,
    )
    manager.save_workflow_checkpoint(workflow_id, context, agent_name="REJECTED", status="REJECTED", execution_summary={"status": "rejected"})
    return {"workflow_id": workflow_id, "status": "REJECTED", "context": context.to_dict()}


@router.post("/workflows/{workflow_id}/request-changes")
def request_changes_workflow(workflow_id: int, payload: WorkflowApprovalRequest):
    from app.orchestration.execution_manager import ExecutionManager

    manager = ExecutionManager()
    workflow = manager.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    if workflow.status not in {"WAITING_FOR_APPROVAL", "PENDING", "APPROVED"}:
        raise HTTPException(status_code=409, detail="Workflow is not awaiting approval.")

    context = manager.get_workflow_context(workflow_id)
    if context is None:
        raise HTTPException(status_code=404, detail="Workflow checkpoint not found.")

    context.approval_status = "REQUESTED_CHANGES"
    context.approval_notes = payload.notes or "Changes requested by reviewer."
    context.approved_by = payload.approved_by or "human-reviewer"
    manager.record_approval_decision(
        workflow_id,
        "REQUESTED_CHANGES",
        approved_by=context.approved_by,
        notes=context.approval_notes,
        content_hash=context.approval_content_hash,
    )
    manager.save_workflow_checkpoint(workflow_id, context, agent_name="REQUESTED_CHANGES", status="WAITING_FOR_APPROVAL", execution_summary={"status": "requested_changes"})
    return {"workflow_id": workflow_id, "status": "WAITING_FOR_APPROVAL", "context": context.to_dict()}


@router.get("/workflows/{workflow_id}")
def get_workflow_status(workflow_id: int):
    from app.orchestration.execution_manager import ExecutionManager

    manager = ExecutionManager()
    workflow = manager.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found.")

    return {
        "workflow_id": workflow.id,
        "campaign_topic": workflow.campaign_topic,
        "status": workflow.status,
        "error_message": workflow.error_message,
        "execution_summary": workflow.execution_summary,
    }


@router.post("/workflows/{workflow_id}/retry")
def retry_workflow(workflow_id: int):
    from app.orchestration.execution_manager import ExecutionManager

    manager = ExecutionManager()
    workflow = manager.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found.")

    try:
        engine = WorkflowEngine()
        context = engine.resume_workflow(workflow_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    persisted = manager.get_workflow(workflow_id)
    return {
        "workflow_id": workflow_id,
        "status": persisted.status if persisted is not None else "FAILED",
        "context": context.to_dict(),
    }


@router.post("/workflows/{workflow_id}/resume")
def resume_workflow(workflow_id: int):
    return retry_workflow(workflow_id)
