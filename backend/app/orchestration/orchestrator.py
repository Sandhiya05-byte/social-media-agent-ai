from __future__ import annotations

from typing import Any

from app.orchestration.workflow_context import WorkflowContext
from app.orchestration.workflow_engine import WorkflowEngine


class CentralAgentOrchestrator:
    def __init__(self, workflow_engine: WorkflowEngine | None = None):
        self.workflow_engine = workflow_engine or WorkflowEngine()

    def create_context(
        self,
        creator_id: int | None = None,
        campaign_topic: str = "",
        target_audience: str = "general audience",
        platforms: list[str] | None = None,
        campaign_objective: str = "content growth",
        content_type: str = "short-form",
        brand_voice: dict[str, Any] | None = None,
        competitor_urls: list[str] | None = None,
        rss_sources: list[str] | None = None,
        creator_writing_samples: list[str] | None = None,
    ) -> WorkflowContext:
        context = WorkflowContext(
            creator_id=creator_id,
            campaign_topic=campaign_topic,
            target_audience=target_audience,
            platforms=platforms or ["Instagram"],
            campaign_objective=campaign_objective,
            content_type=content_type,
            brand_voice=brand_voice or {},
            research_findings={"rss_sources": rss_sources or []},
            competitor_findings={"competitor_urls": competitor_urls or []},
            hooks=[],
        )
        if creator_writing_samples:
            context.brand_voice = {
                "samples": creator_writing_samples,
                "voice_profile": context.brand_voice.get("voice_profile", {}),
            }
        return context

    def run(self, **kwargs) -> WorkflowContext:
        context = self.create_context(**kwargs)
        return self.workflow_engine.run(context)
