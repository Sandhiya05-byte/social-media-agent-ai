export default async function run(page, ui) {
  const results = {};

  // The review board is always in the DOM (single-page App.jsx); no nav needed.
  await page.waitForTimeout(800);

  results.videoElements = await page.evaluate(() => document.querySelectorAll("video").length);
  results.videoSrcs = await page.evaluate(() =>
    Array.from(document.querySelectorAll("video")).map((v) => v.getAttribute("src")),
  );
  results.thumbnailImgs = await page.evaluate(() =>
    Array.from(document.querySelectorAll("img"))
      .map((i) => i.getAttribute("src"))
      .filter((s) => s && (s.includes("_thumb") || s.includes("/generated/"))),
  );
  results.subtitleLinks = await page.evaluate(() =>
    Array.from(document.querySelectorAll("a"))
      .map((a) => a.textContent)
      .filter((t) => t && t.includes("subtitles")),
  );

  // Check the review board shows the queue item bridged earlier.
  results.reviewBoardText = await page.evaluate(() => {
    const h = Array.from(document.querySelectorAll("h3")).find((el) =>
      el.textContent.includes("Human Review Board"),
    );
    if (!h) return null;
    const panel = h.closest("div.rounded-3xl");
    return panel ? panel.innerText.slice(0, 600) : null;
  });

  // Approve/Reject/Request changes buttons present?
  results.actionButtons = await page.evaluate(() =>
    Array.from(document.querySelectorAll("button"))
      .map((b) => b.textContent.trim())
      .filter((t) => ["Approve", "Reject", "Request changes"].includes(t)),
  );

  return results;
}
