from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.orchestration.orchestrator import CentralAgentOrchestrator

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

    return {"workflow_id": context.workflow_id, "status": "completed", "context": context.to_dict()}


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
