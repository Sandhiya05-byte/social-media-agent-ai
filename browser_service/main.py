import os
from urllib.parse import urlencode, urlparse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query

load_dotenv(Path(__file__).with_name(".env"))

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "").strip()
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

app = FastAPI(
    title="Social Media Research Service",
    description="Public web and YouTube research for the Social Media Agent.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "service": "browser_service",
        "youtube_configured": bool(YOUTUBE_API_KEY),
    }


@app.get("/research/youtube")
async def research_youtube(
    query: str = Query(..., min_length=2, max_length=200),
    max_results: int = Query(default=10, ge=1, le=50),
) -> dict[str, Any]:

    if not YOUTUBE_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="YouTube API key is not configured.",
        )

    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "order": "relevance",
        "maxResults": max_results,
        "key": YOUTUBE_API_KEY,
    }

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.get(YOUTUBE_SEARCH_URL, params=params)

        data = response.json()

        if response.status_code != 200:
            errors = data.get("error", {}).get("errors", [])
            reason = errors[0].get("reason", "") if errors else ""

            if reason == "quotaExceeded":
                raise HTTPException(
                    status_code=429,
                    detail="YouTube API daily quota exceeded.",
                )

            if reason in ("keyInvalid", "accessNotConfigured"):
                raise HTTPException(
                    status_code=503,
                    detail="YouTube API key is invalid or the API is not enabled.",
                )

            raise HTTPException(
                status_code=502,
                detail="YouTube API returned an error. Check API configuration.",
            )

        results = []

        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            video_id = item.get("id", {}).get("videoId")

            if not video_id:
                continue

            results.append({
                "video_id": video_id,
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "channel": snippet.get("channelTitle", ""),
                "channel_id": snippet.get("channelId", ""),
                "published_at": snippet.get("publishedAt", ""),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail": (
                    snippet.get("thumbnails", {})
                    .get("high", {})
                    .get("url", "")
                ),
            })

        return {
            "status": "success",
            "source": "youtube",
            "query": query,
            "result_count": len(results),
            "results": results,
        }

    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="YouTube API request timed out.",
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Could not connect to YouTube API.",
        )
    except ValueError:
        raise HTTPException(
            status_code=502,
            detail="YouTube API returned an invalid response.",
        )
async def _search_via_browser(page: Any, search_url: str, source_name: str, max_results: int) -> dict[str, Any]:
    """Run one search-engine query in an existing Playwright page.

    Returns the normal result dict. Honest about blocks, timeouts and empty
    result pages — nothing is fabricated.
    """
    # Engine-specific result-link selectors, plus a general fallback.
    selectors = {
        "google_search": "a:has(h3)",
        "duckduckgo_html": "a.result__a",
        "bing_search": "li.b_algo h2 a",
    }
    link_selector = selectors.get(source_name, "a:has(h3)")

    await page.goto(search_url, wait_until="domcontentloaded", timeout=25000)
    await page.wait_for_timeout(3000)

    page_text = (await page.locator("body").inner_text()).lower()

    block_terms = [
        "unusual traffic",
        "our systems have detected",
        "not a robot",
        "captcha",
        "verify you are human",
        "verify you're human",
        "confirm you are human",
    ]
    # Only treat it as a block when real result links are absent — the block
    # terms can otherwise appear inside ordinary result pages.
    if any(term in page_text for term in block_terms):
        link_count = await page.locator(link_selector).count()
        if link_count == 0:
            return {
                "status": "blocked",
                "source": source_name,
                "result_count": 0,
                "results": [],
                "limitation": f"{source_name} displayed an automated-traffic verification page.",
            }

    # Engine-agnostic extraction: prefer engine-specific selectors, then fall
    # back to scanning all anchors for genuine external result links.
    links = await page.locator(link_selector).all()
    if not links:
        links = await page.locator("a[href]").all()

    results = []
    seen_urls = set()

    for link in links:
        if len(results) >= max_results:
            break
        try:
            item = await link.evaluate(
                """a => ({
                    url: a.href,
                    title: (a.querySelector('h3')?.innerText || a.innerText || '').trim(),
                    text: a.innerText || ''
                })"""
            )
            url = item.get("url", "")
            title = item.get("title", "").strip()
            if not title or not url:
                continue

            # Bing wraps result URLs in bing.com/ck/a redirects with the real
            # target base64-encoded in the u=a1... query parameter. Decode it
            # so results point at the actual page.
            if "bing.com/ck/a" in url:
                from base64 import urlsafe_b64decode

                try:
                    from urllib.parse import parse_qs, urlparse as _urlparse

                    query_params = parse_qs(_urlparse(url).query)
                    encoded = (query_params.get("u") or [""])[0]
                    if encoded.startswith("a1"):
                        padded = encoded[2:] + "=" * (-len(encoded[2:]) % 4)
                        decoded = urlsafe_b64decode(padded).decode("utf-8", "ignore")
                        if decoded.startswith("http"):
                            url = decoded
                except Exception:
                    pass

            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                continue
            hostname = parsed.hostname.lower()
            # Skip the search engine's own domain and any redirect-wrapped
            # internal links so only genuine external results are kept.
            if hostname.endswith(("google.com", "duckduckgo.com", "bing.com", "bing.net", "microsoft.com")):
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)
            results.append(
                {
                    "title": title,
                    "url": url,
                    "snippet": item.get("text", "")[:500],
                    "publisher": hostname,
                }
            )
        except Exception:
            continue

    return {
        "status": "success" if results else "no_results",
        "source": source_name,
        "result_count": len(results),
        "results": results,
        "limitation": None if results else "No result links were found on the page.",
    }


@app.get("/research/web")
async def research_web(
    query: str = Query(..., min_length=2, max_length=200),
    max_results: int = Query(default=10, ge=1, le=20),
) -> dict[str, Any]:

    from playwright.async_api import async_playwright

    # Primary: Google. Fallback: DuckDuckGo HTML (public search page). Each
    # attempt is reported with its own status; nothing is fabricated.
    attempts = [
        ("https://www.google.com/search?" + urlencode({"q": query, "num": max_results}), "google_search"),
        ("https://html.duckduckgo.com/html/?" + urlencode({"q": query}), "duckduckgo_html"),
        ("https://www.bing.com/search?" + urlencode({"q": query}), "bing_search"),
    ]

    attempt_log: list[dict[str, Any]] = []

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page(
                    viewport={"width": 1365, "height": 900},
                    locale="en-US",
                )

                for search_url, source_name in attempts:
                    try:
                        outcome = await _search_via_browser(page, search_url, source_name, max_results)
                    except Exception as exc:  # noqa: BLE001 - per-engine failure
                        outcome = {
                            "status": "failed",
                            "source": source_name,
                            "result_count": 0,
                            "results": [],
                            "limitation": str(exc)[:200],
                        }
                    attempt_log.append({"source": source_name, "status": outcome["status"], "limitation": outcome.get("limitation")})
                    if outcome["status"] == "success":
                        return {
                            "status": "success",
                            "source": source_name,
                            "query": query,
                            "result_count": outcome["result_count"],
                            "results": outcome["results"],
                            "limitation": None,
                            "attempts": attempt_log,
                        }

                blocked = any(a["status"] == "blocked" for a in attempt_log)
                return {
                    "status": "blocked" if blocked else "no_results",
                    "source": attempt_log[-1]["source"] if attempt_log else "none",
                    "query": query,
                    "result_count": 0,
                    "results": [],
                    "limitation": "; ".join(f"{a['source']}: {a['limitation'] or a['status']}" for a in attempt_log),
                    "attempts": attempt_log,
                }
            finally:
                await browser.close()

    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Playwright is not installed in the Browser Service environment.",
        )

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Public web research unavailable: {str(exc)[:250]}",
        )