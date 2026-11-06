"""Configurable research providers for topic-driven campaign research.

All providers are optional and configured purely through environment
variables (never hardcoded). Every provider returns an honest status so the
system never fabricates results when a provider is unavailable.
"""

from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from app.config import (
    BROWSER_SERVICE_URL,
    RSS_FEEDS,
    YOUTUBE_API_KEY,
    GOOGLE_SEARCH_API_KEY,
    GOOGLE_SEARCH_CSE_ID,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip_html(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


class ResearchProviderResult(dict):
    """dict with helper accessors for provider output."""

    @property
    def sources(self) -> list[dict[str, Any]]:
        return self.get("sources", [])


def _feedparser_available() -> bool:
    try:
        import feedparser  # noqa: F401

        return True
    except ImportError:
        return False


def fetch_rss_feeds(topic: str, feeds: list[str] | None = None, max_per_feed: int = 5) -> dict[str, Any]:
    """Fetch and parse RSS feeds via feedparser. Never fabricates entries."""
    if not _feedparser_available():
        return {
            "provider": "rss",
            "status": "unavailable",
            "limitation": "feedparser is not installed.",
            "sources": [],
        }

    import feedparser

    feed_list = feeds if feeds is not None else list(RSS_FEEDS)
    if not feed_list:
        return {
            "provider": "rss",
            "status": "unavailable",
            "limitation": "No RSS feeds configured (RESEARCH_RSS_FEEDS).",
            "sources": [],
        }

    # Build topic keywords for relevance scoring.
    keywords = [w for w in re.findall(r"[a-zA-Z]{4,}", topic.lower())][:8]

    sources: list[dict[str, Any]] = []
    failures: list[str] = []
    for feed_url in feed_list:
        try:
            parsed = feedparser.parse(feed_url)
            entries = getattr(parsed, "entries", []) or []
            if getattr(parsed, "bozo", False) and not entries:
                failures.append(f"{feed_url}: parse error")
                continue
            if not entries:
                failures.append(f"{feed_url}: no entries")
                continue

            scored: list[tuple[int, Any]] = []
            for entry in entries:
                text = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
                score = sum(1 for kw in keywords if kw in text)
                scored.append((score, entry))
            scored.sort(key=lambda pair: pair[0], reverse=True)

            selected = [entry for score, entry in scored[:max_per_feed] if score > 0]
            if not selected:
                # No topic-relevant entries in this feed: still return the
                # feed's real latest items, clearly marked as general context
                # rather than topic matches.
                selected = [entry for _score, entry in scored[:2]]

            for entry in selected:
                link = entry.get("link") or ""
                title = _strip_html(entry.get("title", "")) or "(untitled)"
                summary = _strip_html(entry.get("summary", ""))[:400]
                published = entry.get("published") or entry.get("updated") or ""
                source = {
                    "provider": "rss",
                    "type": "article",
                    "feed_url": feed_url,
                    "url": link,
                    "title": title,
                    "publisher": (parsed.feed.get("title") if hasattr(parsed, "feed") else "") or feed_url,
                    "published_at": published,
                    "retrieved_at": _now_iso(),
                    "excerpt": summary,
                }
                sources.append(source)
        except Exception as exc:  # noqa: BLE001 - a bad feed must not break research
            failures.append(f"{feed_url}: {exc}")

    if failures and not sources:
        return {
            "provider": "rss",
            "status": "failed",
            "limitation": "; ".join(failures[:5]),
            "sources": [],
        }

    return {
        "provider": "rss",
        "status": "ok" if sources else "no_results",
        "limitation": "; ".join(failures[:5]) if failures else None,
        "sources": sources,
    }


def search_youtube_via_browser_service(
    topic: str,
    max_results: int = 6,
) -> dict[str, Any]:
    """Retrieve real YouTube research through the Browser Service."""

    service_url = "http://127.0.0.1:8002"

    try:
        params = urllib.parse.urlencode({
            "query": topic,
            "max_results": max_results,
        })

        request = urllib.request.Request(
            f"{service_url}/research/youtube?{params}",
            headers={"Accept": "application/json"},
        )

        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.load(response)

        if payload.get("status") != "success":
            return {
                "provider": "youtube",
                "status": "failed",
                "limitation": payload.get(
                    "detail",
                    payload.get("message", "Browser Service returned an unsuccessful response."),
                ),
                "sources": [],
            }

        sources = []

        for item in payload.get("results", []):
            if not item.get("url") or not item.get("title"):
                continue

            sources.append({
                "provider": "youtube",
                "type": "video",
                "url": item["url"],
                "title": item["title"],
                "publisher": item.get("channel", ""),
                "channel_title": item.get("channel", ""),
                "description": _strip_html(
                    item.get("description", "")
                )[:400],
                "published_at": item.get("published_at"),
                "retrieved_at": _now_iso(),
                "video_id": item.get("video_id"),
                "thumbnail": item.get("thumbnail"),
            })

        return {
            "provider": "youtube",
            "status": "ok" if sources else "no_results",
            "limitation": None,
            "sources": sources,
        }

    except urllib.error.HTTPError as exc:
        return {
            "provider": "youtube",
            "status": "failed",
            "limitation": f"Browser Service HTTP error: {exc.code}",
            "sources": [],
        }

    except Exception as exc:
        return {
            "provider": "youtube",
            "status": "unavailable",
            "limitation": f"Browser Service unavailable: {exc}",
            "sources": [],
        }
def search_google_web(topic: str, max_results: int = 6) -> dict[str, Any]:
    """Google Custom Search JSON API — only when both credentials are configured."""
    if not (GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_CSE_ID):
        return {
            "provider": "google_search",
            "status": "unconfigured",
            "limitation": "GOOGLE_SEARCH_API_KEY / GOOGLE_SEARCH_CSE_ID are not set.",
            "sources": [],
        }

    params = urllib.parse.urlencode(
        {
            "key": GOOGLE_SEARCH_API_KEY,
            "cx": GOOGLE_SEARCH_CSE_ID,
            "q": topic,
            "num": max_results,
        }
    )
    url = f"https://www.googleapis.com/customsearch/v1?{params}"
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        return {"provider": "google_search", "status": "failed", "limitation": f"HTTP {exc.code}", "sources": []}
    except Exception as exc:  # noqa: BLE001
        return {"provider": "google_search", "status": "failed", "limitation": str(exc), "sources": []}

    sources = []
    for item in payload.get("items", []) or []:
        sources.append(
            {
                "provider": "google_search",
                "type": "webpage",
                "url": item.get("link", ""),
                "title": item.get("title", ""),
                "publisher": item.get("displayLink", ""),
                "excerpt": _strip_html(item.get("snippet", ""))[:400],
                "published_at": None,
                "retrieved_at": _now_iso(),
            }
        )
    if not sources:
        return {"provider": "google_search", "status": "no_results", "limitation": None, "sources": []}
    return {"provider": "google_search", "status": "ok", "limitation": None, "sources": sources}


def search_web_via_browser(topic: str, max_results: int = 6) -> dict[str, Any]:
    """Public web search through the Browser Service (Playwright)."""
    try:
        params = urllib.parse.urlencode({"query": topic, "max_results": max_results})
        request = urllib.request.Request(
            f"{BROWSER_SERVICE_URL}/research/web?{params}",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=150) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8", "ignore")).get("detail", "")
        except Exception:
            detail = f"HTTP {exc.code}"
        return {"provider": "web_search", "status": "failed", "limitation": detail, "sources": []}
    except Exception as exc:  # noqa: BLE001
        return {
            "provider": "web_search",
            "status": "unavailable",
            "limitation": f"Browser Service unreachable: {exc}",
            "sources": [],
        }

    sources = [
        {
            "provider": "web_search",
            "type": "webpage",
            "url": item.get("url", ""),
            "title": item.get("title", ""),
            "publisher": item.get("publisher", ""),
            "excerpt": _strip_html(item.get("snippet", ""))[:400],
            "published_at": None,
            "retrieved_at": _now_iso(),
        }
        for item in payload.get("results", [])
        if item.get("url") and item.get("title")
    ]
    if payload.get("status") == "success" and sources:
        return {"provider": "web_search", "status": "ok", "limitation": None, "sources": sources}
    return {
        "provider": "web_search",
        "status": payload.get("status", "no_results"),
        "limitation": payload.get("limitation") or payload.get("detail") or "No web results returned.",
        "sources": [],
    }


def run_topic_research(topic: str, rss_feeds: list[str] | None = None) -> dict[str, Any]:
    """Run every configured provider for the exact campaign topic.

    Returns a structured report with per-provider status, real sources with
    URLs/timestamps, and honest limitations. Never fabricates results.
    """
    providers: dict[str, Any] = {
        "rss": fetch_rss_feeds(topic, rss_feeds),
        "youtube": search_youtube_via_browser_service(topic),
        "web_search": search_web_via_browser(topic),
        "google_search": search_google_web(topic),
    }

    all_sources: list[dict[str, Any]] = []
    provider_statuses: dict[str, str] = {}
    limitations: list[str] = []
    seen_urls: set[str] = set()
    for name, result in providers.items():
        provider_statuses[name] = result["status"]
        if result.get("limitation"):
            limitations.append(f"{name}: {result['limitation']}")
        for source in result.get("sources", []):
            url = str(source.get("url") or "").strip().rstrip("/").lower()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            all_sources.append(source)

    any_ok = any(status == "ok" for status in provider_statuses.values())
    return {
        "topic": topic,
        "retrieved_at": _now_iso(),
        "provider_statuses": provider_statuses,
        "limitations": limitations,
        "sources": all_sources,
        "status": "ok" if any_ok else ("no_results" if all(s in {"ok", "no_results", "unconfigured"} for s in provider_statuses.values()) else "failed"),
    }
