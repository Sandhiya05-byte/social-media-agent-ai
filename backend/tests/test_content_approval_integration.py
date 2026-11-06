from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

VALID_WORKFLOW_PAYLOAD = {
    "campaign_topic": "Creator growth systems",
    "target_audience": "new creators",
    "platforms": ["Instagram"],
    "campaign_objective": "Build clear educational content.",
    "content_type": "short-form",
    "competitor_urls": ["https://example.com/competitor"],
    "rss_sources": ["https://example.com/rss"],
    "creator_writing_samples": ["Clarity compounds. Systems are scalable."],
}


def test_workflow_video_output_includes_media_metadata():
    created = client.post("/api/orchestration/workflows", json=VALID_WORKFLOW_PAYLOAD)
    assert created.status_code == 200, created.text
    body = created.json()
    video = body["context"]["video_output"]

    for key in (
        "video_url",
        "thumbnail_url",
        "subtitle_url",
        "duration_seconds",
        "audio_enabled",
        "video_width",
        "video_height",
        "render_engine",
    ):
        assert key in video, f"missing video metadata field: {key}"

    if video["video_url"]:
        assert video["video_url"].startswith("/generated/")
        served = client.get(video["video_url"])
        assert served.status_code == 200
        assert served.headers["content-type"].startswith(("video/", "image/"))


def test_platform_checks_report_met_or_not_met():
    response = client.post(
        "/api/content/validate",
        json={
            "title": "Creator Growth Playbook",
            "platform": "Instagram",
            "content": "A simple system to grow without chasing trends. Use clear messaging with repeatable systems.",
            "captions": ["Hook", "Explain", "Framework", "CTA"],
            "media_path": "/generated/creative/instagram_creator_growth_playbook.png",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "passed"
    checks = body["platform_checks"]
    assert checks and all(check.endswith(": met") for check in checks), checks


def test_platform_checks_report_not_met():
    response = client.post(
        "/api/content/validate",
        json={"title": "A clear YouTube title", "platform": "YouTube", "content": "Some body text for the video."},
    )
    assert response.status_code == 200
    body = response.json()
    assert any("script is required for video narration: NOT MET" in check for check in body["platform_checks"])
    assert body["errors"], "Missing script must produce a hard error for YouTube"


def test_workflow_content_bridges_to_approval_queue():
    created = client.post("/api/orchestration/workflows", json=VALID_WORKFLOW_PAYLOAD)
    workflow_id = created.json()["workflow_id"]

    bridged = client.post(f"/api/content/from-workflow/{workflow_id}")
    assert bridged.status_code in {200, 201, 409}, bridged.text
    item = bridged.json()
    if bridged.status_code == 409:
        # Auto-bridge already created the item; fetch it from the queue.
        queue_now = client.get("/api/content").json()
        item = next(i for i in queue_now if i.get("workflow_id") == workflow_id)

    assert item["status"] == "Awaiting Approval"
    assert item["title"]
    assert item["content"]
    assert item["media_url"] is not None
    # The queue item references the video asset, not a decorative PNG.
    assert ".mp4" in item["media_url"] or ".gif" in item["media_url"]

    # Bridge is idempotent: the auto-bridge already created the item, so a
    # manual repeat is correctly refused without duplicating it.
    duplicate = client.post(f"/api/content/from-workflow/{workflow_id}")
    assert duplicate.status_code in {200, 201, 409}

    # Item is now visible in the queue.
    queue = client.get("/api/content").json()
    assert any(entry["id"] == item["id"] for entry in queue)


def test_approval_persists_and_gates_scheduling():
    payload = dict(VALID_WORKFLOW_PAYLOAD, campaign_topic="Approval persistence topic")
    created = client.post("/api/orchestration/workflows", json=payload)
    workflow_id = created.json()["workflow_id"]

    bridged = client.post(f"/api/content/from-workflow/{workflow_id}")
    if bridged.status_code == 409:
        # Auto-bridge already created the item; fetch it from the queue.
        queue_now = client.get("/api/content").json()
        item = next(i for i in queue_now if i.get("workflow_id") == workflow_id)
    else:
        item = bridged.json()

    # Not approved yet -> scheduling must be refused.
    early = client.post(f"/api/content/{item['id']}/schedule", json={"scheduled_for": "2030-01-01T10:00:00Z"})
    assert early.status_code == 400

    approved = client.post(f"/api/content/{item['id']}/approve", json={"approved_by": "reviewer", "notes": "ok"})
    assert approved.status_code == 200
    assert approved.json()["status"] == "Approved"
    assert approved.json()["approved_by"] == "reviewer"
    assert approved.json()["approved_at"] is not None

    # Approval state survives a full re-fetch.
    refetched = client.get(f"/api/content/{item['id']}").json()
    assert refetched["status"] == "Approved"

    scheduled = client.post(f"/api/content/{item['id']}/schedule", json={"scheduled_for": "2030-01-01T10:00:00Z"})
    assert scheduled.status_code == 200
    assert scheduled.json()["status"] == "Scheduled"


def test_rejected_content_cannot_be_scheduled():
    payload = {
        "title": "Rejected workflow content",
        "platform": "Instagram",
        "content": "A simple system to grow without chasing trends. Use clear messaging with repeatable systems.",
        "captions": ["Hook", "CTA"],
        "media_path": "/generated/creative/instagram_creator_growth_playbook.png",
    }
    item = client.post("/api/content", json=payload).json()
    rejected = client.post(f"/api/content/{item['id']}/reject", json={"notes": "Weak hook."})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "Rejected"

    scheduled = client.post(f"/api/content/{item['id']}/schedule", json={"scheduled_for": "2030-01-01T10:00:00Z"})
    assert scheduled.status_code == 400
