from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.agents.brand_voice_agent import BrandVoiceAgent
from app.agents.competitor_intelligence_agent import CompetitorIntelligenceAgent
from app.agents.hook_generation_agent import HookGenerationAgent
from app.agents.trend_research_agent import TrendResearchAgent


class ResearchWorkflow:
    def __init__(self):
        self.trend_agent = TrendResearchAgent()
        self.competitor_agent = CompetitorIntelligenceAgent()
        self.voice_agent = BrandVoiceAgent()
        self.hook_agent = HookGenerationAgent()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def run(self, niche: str, competitor_urls: list[str] | None = None, creator_writing_samples: list[str] | None = None, rss_sources: list[str] | None = None) -> dict[str, Any]:
        competitor_urls = competitor_urls or []
        creator_writing_samples = creator_writing_samples or []
        rss_sources = rss_sources or []

        trend_result = self.trend_agent.execute(niche=niche, source_urls=rss_sources)
        competitor_result = self.competitor_agent.execute(niche=niche, competitor_urls=competitor_urls)
        voice_result = self.voice_agent.execute(niche=niche, creator_samples=creator_writing_samples)
        hook_result = self.hook_agent.execute(niche=niche, creator_style=voice_result.get("voice_profile", {}))

        content_gap_suggestions = [
            {
                "title": f"Create a clear {niche} framework for beginners",
                "why_it_matters": "Competitors explain concepts, but fewer creators give a practical roadmap with examples.",
                "source_url": competitor_urls[0] if competitor_urls else "https://example.com/public-competitor-source",
                "published_at": self._now(),
            },
            {
                "title": f"Turn ideas into weekly {niche} experiments",
                "why_it_matters": "A repeatable sequence is easier to trust than raw inspiration alone.",
                "source_url": competitor_urls[1] if len(competitor_urls) > 1 else "https://example.com/public-competitor-source",
                "published_at": self._now(),
            },
        ]

        scripts = [
            {
                "title": f"{niche} script: the simple weekly system",
                "script": f"In this week's {niche} strategy, the real win is not chasing more ideas. It is building one system that keeps your content consistent and your message clear.",
                "source_url": competitor_urls[0] if competitor_urls else "https://example.com/creator-voice-source",
                "published_at": self._now(),
            },
            {
                "title": f"{niche} script: transformation and proof",
                "script": f"Most people think {niche} is about having a perfect angle. The truth is, the breakthrough happens when you document the process and share the proof.",
                "source_url": competitor_urls[1] if len(competitor_urls) > 1 else "https://example.com/creator-voice-source",
                "published_at": self._now(),
            },
        ]

        agent_statuses = [
            {"agent": trend_result["agent"], "status": trend_result["status"], "started_at": trend_result.get("started_at"), "completed_at": trend_result.get("completed_at"), "summary": trend_result.get("summary"), "source_urls": trend_result.get("source_urls")},
            {"agent": competitor_result["agent"], "status": competitor_result["status"], "started_at": competitor_result.get("started_at"), "completed_at": competitor_result.get("completed_at"), "summary": competitor_result.get("summary"), "source_urls": competitor_result.get("competitor_urls")},
            {"agent": voice_result["agent"], "status": voice_result["status"], "started_at": voice_result.get("started_at"), "completed_at": voice_result.get("completed_at"), "summary": voice_result.get("summary"), "source_urls": voice_result.get("creator_samples")},
            {"agent": hook_result["agent"], "status": hook_result["status"], "started_at": hook_result.get("started_at"), "completed_at": hook_result.get("completed_at"), "summary": hook_result.get("summary")},
        ]

        return {
            "workflow_id": f"research-{int(datetime.now(timezone.utc).timestamp())}",
            "status": "completed",
            "agent_statuses": agent_statuses,
            "ranked_topic_suggestions": trend_result.get("ranked_topic_suggestions", []),
            "competitor_observations": competitor_result.get("observations", []),
            "content_gap_suggestions": content_gap_suggestions,
            "creator_style_scripts": scripts,
            "hook_alternatives": hook_result.get("hook_alternatives", []),
        }
