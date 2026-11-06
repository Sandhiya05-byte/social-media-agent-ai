from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.research import ResearchRequest, ResearchResponse
from app.services.research_workflow import ResearchWorkflow

router = APIRouter(prefix="/api/research", tags=["research"])


@router.post("/workflow", response_model=ResearchResponse)
def run_research_workflow(payload: ResearchRequest):
    if not payload.niche.strip():
        raise HTTPException(status_code=400, detail="Niche is required.")

    workflow = ResearchWorkflow()
    result = workflow.run(
        niche=payload.niche,
        competitor_urls=payload.competitor_urls,
        creator_writing_samples=payload.creator_writing_samples,
        rss_sources=payload.rss_sources,
    )
    return result
