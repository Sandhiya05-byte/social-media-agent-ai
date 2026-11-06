from __future__ import annotations

import re
import urllib.request
from typing import Any

from app.agents.base import BaseAgent  # noqa: circular-safe

def _fetch_page_text(url: str, limit: int = 3000) -> str | None:
    """Fetch a public page's text content. Returns None on any failure."""
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "WoverseResearch/1.0 (+local automation)"},
        )
        with urllib.request.urlopen(request, timeout=12) as response:
            body = response.read(limit * 4).decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001 - unreachable sites are expected
        return None
    import html as html_module

    body = re.sub(r"<script[\s\S]*?</script>", " ", body, flags=re.I)
    body = re.sub(r"<style[\s\S]*?</style>", " ", body, flags=re.I)
    text = re.sub(r"\s+", " ", html_module.unescape(re.sub(r"<[^>]+>", " ", body)))
    return text[:limit] or None


class CompetitorIntelligenceAgent(BaseAgent):
    name = "Competitor Intelligence Agent"

    def execute(self, niche: str, competitor_urls: list[str] | None = None, research_results: dict | None = None, **kwargs) -> dict[str, Any]:
        self.status = "running"
        started_at = self._now()

        user_supplied = [u for u in (competitor_urls or []) if str(u).strip()]
        observations: list[dict[str, Any]] = []
        source_references: list[dict[str, Any]] = []

        # 1) Analyze user-supplied competitor URLs (real retrieval, honest on failure).
        for url in user_supplied[:5]:
            text = _fetch_page_text(url)
            if text:
                source_references.append(
                    {"provider": "direct_fetch", "type": "competitor_page", "url": url, "excerpt": text[:400], "retrieved_at": self._now()}
                )
                observations.append(
                    {
                        "competitor_url": url,
                        "source": "user_supplied",
                        "summary": f"Accessible public page retrieved ({len(text)} chars extracted).",
                        "signal_strength": "Measured",
                    }
                )
            else:
                observations.append(
                    {
                        "competitor_url": url,
                        "source": "user_supplied",
                        "summary": "URL could not be retrieved (unreachable or blocked); no claims made.",
                        "signal_strength": "Unavailable",
                    }
                )

        # 2) Discover relevant competitors from live research when none supplied.
        discovered: list[dict[str, Any]] = []
        research_sources = (research_results or {}).get("source_references") or []
        if not user_supplied:
            # Actual competitors are topic-specific YouTube videos and web pages
            # returned by the research providers. General news (RSS) sources are
            # NOT competitors — they are context only and are excluded here.
            youtube_hits = [s for s in research_sources if s.get("provider") == "youtube"]
            web_hits = [s for s in research_sources if s.get("provider") == "web_search"]
            discovered = (youtube_hits + web_hits)[:6]

            for source in discovered:
                title = source.get("title") or ""
                publisher = source.get("publisher") or source.get("channel_title") or source.get("feed_url") or ""
                source_references.append({**source, "type": "discovered_competitor"})
                observations.append(
                    {
                        "competitor_url": source.get("url"),
                        "source": "discovered",
                        "summary": f"Public coverage: {title[:120]} (publisher: {publisher[:80]}).",
                        "signal_strength": "Measured",
                    }
                )

        # 3) Content-gap inference, labelled as inference — always present so
        # downstream agents receive at least one honest finding.
        if user_supplied or discovered:
            measured = [o for o in observations if o["signal_strength"] == "Measured"]
            observations.append(
                {
                    "competitor_url": None,
                    "source": "inference",
                    "summary": (
                        f"Content-gap inference from {len(measured)} measured sources: prioritize "
                        f"topic-specific, example-led explainers for '{niche}' rather than generic overviews."
                    ),
                    "signal_strength": "Inference",
                }
            )
        else:
            observations.append(
                {
                    "competitor_url": None,
                    "source": "inference",
                    "summary": (
                        f"No competitor sources were reachable for '{niche}' (no URLs supplied and "
                        "no research results available); no competitor claims are made."
                    ),
                    "signal_strength": "Unavailable",
                }
            )

        self.status = "completed"
        return {
            "agent": self.name,
            "status": self.status,
            "started_at": started_at,
            "completed_at": self._now(),
            "niche": niche,
            "user_supplied_urls": user_supplied,
            "discovered_sources_count": len(discovered),
            "competitor_urls": user_supplied or [s.get("url") for s in discovered[:5]],
            "observations": observations,
            "source_references": source_references,
            "summary": (
                f"Competitor intelligence for '{niche}': {len(user_supplied)} supplied, "
                f"{len(discovered)} discovered, {len(source_references)} sources analyzed."
            ),
        }
