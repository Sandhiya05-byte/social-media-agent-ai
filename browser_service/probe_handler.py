"""Direct functional test of the /research/web handler logic (no HTTP)."""
import asyncio
import sys
from urllib.parse import urlencode

sys.path.insert(0, r"D:\Social_media_Agent_AI\browser_service")

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1365, "height": 900}, locale="en-US")
        await page.goto("https://www.bing.com/search?" + urlencode({"q": "best AI tools for college students"}), wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(3000)
        links = await page.locator("li.b_algo h2 a").all()
        print("link count:", len(links))
        for link in links[:3]:
            try:
                item = await link.evaluate(
                    """a => ({
                        url: a.href,
                        title: (a.querySelector('h3')?.innerText || a.innerText || '').trim(),
                        text: a.innerText || ''
                    })"""
                )
                print("  item:", item.get("url", "")[:60], "|", item.get("title", "")[:50])
            except Exception as exc:
                print("  evaluate failed:", str(exc)[:150])
        await browser.close()


asyncio.run(main())
