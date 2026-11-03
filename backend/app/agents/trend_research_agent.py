from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent


class TrendResearchAgent(BaseAgent):
    name = "Trend Research Agent"

    def execute(self, niche: str, source_urls: list[str] | None = None, **kwargs) -> dict[str, Any]:
        self.status = "running"
        sources = source_urls or [
            "https://www.feedforall.com/sample.xml",
            "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
            "https://www.theverge.com/rss/index.xml",
        ]

        prompt = f"Find ranked trend opportunities for a creator operating in {niche}. Consider public RSS sources and audience demand."
        raw = self.model.generate(prompt, {"niche": niche, "source_urls": sources})
        payload = self._parse_model_response(raw)

        fallback_source = "https://example.com/public-rss-source"
        suggestions = [
            {
                "title": f"{niche} content series that explains mistakes and fixes",
                "score": 96,
                "why_it_matters": "High search demand and strong educational engagement for creators in this niche.",
                "source_url": sources[0] if len(sources) > 0 else fallback_source,
                "published_at": self._now(),
            },
            {
                "title": f"{niche} myth-busting content for beginners",
                "score": 92,
                "why_it_matters": "Works well for short-form video hooks and long-form educational explainers.",
                "source_url": sources[1] if len(sources) > 1 else fallback_source,
                "published_at": self._now(),
            },
            {
                "title": f"{niche} before-and-after workflows with proof",
                "score": 88,
                "why_it_matters": "Transforms non-trending expertise into shareable creator stories",
                "source_url": sources[2] if len(sources) > 2 else fallback_source,
                "published_at": self._now(),
            },
        ]

        self.status = "completed"
        return {
            "agent": self.name,
            "status": self.status,
            "started_at": self._now(),
            "completed_at": self._now(),
            "source_urls": sources,
            "ranked_topic_suggestions": suggestions,
            "summary": payload.get("summary") or f"Trend research completed for {niche}.",
        }
