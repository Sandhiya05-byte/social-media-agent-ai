from __future__ import annotations

import re
from typing import Any

from app.agents.base import BaseAgent


class TrendResearchAgent(BaseAgent):
    name = "Trend Research Agent"

    def execute(self, niche: str, source_urls: list[str] | None = None, **kwargs) -> dict[str, Any]:
        self.status = "running"
        started_at = self._now()

        # Lazy import: services/__init__ imports the research workflow which
        # imports this module — a module-level import would be circular.
        from app.services.research_providers import run_topic_research

        # Real retrieval for the exact campaign topic. No invented results:
        # every source carries a URL, publisher and retrieval timestamp.
        report = run_topic_research(niche, rss_feeds=source_urls or None)
        sources = report["sources"]

        # Inference layer: clearly labelled as inference, derived only from
        # retrieved source titles/excerpts.
        keywords = sorted(
            {
                word.lower()
                for source in sources
                for word in __import__("re").findall(r"[a-zA-Z]{5,}", f"{source.get('title','')} {source.get('excerpt','')}")
            }
        )[:15]

        trending_subtopics: list[str] = []
        seen: set[str] = set()
        for source in sources:
            title = source.get("title") or ""
            if title and title.lower() not in seen:
                seen.add(title.lower())
                trending_subtopics.append(title)

        observations = [
            {
                "claim": f"Retrieved {len(sources)} public sources matching '{niche}'.",
                "type": "measured",
                "source_urls": [s.get("url") for s in sources[:10]],
            }
        ]
        if keywords:
            observations.append(
                {
                    "claim": f"Most frequent meaningful terms across sources: {', '.join(keywords[:8])}.",
                    "type": "inference",
                    "source_urls": [],
                }
            )

        self.status = "completed"
        return {
            "agent": self.name,
            "status": self.status,
            "started_at": started_at,
            "completed_at": self._now(),
            "niche": niche,
            "topic_summary": f"Live research for '{niche}' across configured providers.",
            "current_developments": [s.get("title", "") for s in sources[:10]],
            "trending_subtopics": trending_subtopics[:10],
            "audience_questions": [],
            "content_opportunities": [],
            "keywords": keywords,
            "observations": observations,
            "source_references": sources,
            "provider_statuses": report["provider_statuses"],
            "provider_limitations": report["limitations"],
            "research_status": report["status"],
            "summary": (
                f"Research for '{niche}': {len(sources)} sources retrieved; "
                f"providers {report['provider_statuses']}."
            ),
        }
