from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

CAMPAIGN_A = {
    "campaign_topic": "AI tools for college students",
    "target_audience": "College students",
    "platforms": ["Instagram", "YouTube"],
    "campaign_objective": "Educate students about useful AI tools.",
    "content_type": "short-form",
}

CAMPAIGN_B = {
    "campaign_topic": "Sustainable fashion for Gen Z",
    "target_audience": "Young adults",
    "platforms": ["Instagram", "YouTube"],
    "campaign_objective": "Show affordable sustainable fashion choices.",
    "content_type": "short-form",
}


def _run_campaign(payload: dict) -> dict:
    created = client.post("/api/orchestration/workflows", json=payload)
    assert created.status_code == 200, created.text
    return created.json()


def test_research_is_topic_driven_and_traceable():
    body = _run_campaign(CAMPAIGN_A)
    research = body["context"]["research_findings"]
    assert "provider_statuses" in research
    assert "source_references" in research
    # Every source is traceable.
    for source in research["source_references"]:
        assert source.get("url")
        assert source.get("retrieved_at")
    # Topic-anchored hooks, not the old generic creator-growth hooks.
    hooks = body["context"]["hooks"]
    assert hooks and any("college students" in h.lower() or "ai tools" in h.lower() for h in hooks)


def test_different_niches_produce_different_outputs():
    a = _run_campaign(CAMPAIGN_A)
    b = _run_campaign(CAMPAIGN_B)

    title_a = a["context"]["creative_output"]["title"]
    title_b = b["context"]["creative_output"]["title"]
    assert title_a != title_b
    assert "college" in title_a.lower() or "ai tool" in title_a.lower()
    assert "fashion" in title_b.lower() or "gen z" in title_b.lower() or "sustainab" in title_b.lower()

    hooks_a = a["context"]["hooks"]
    hooks_b = b["context"]["hooks"]
    assert hooks_a != hooks_b


def test_workflow_auto_creates_content_item_idempotently():
    body = _run_campaign(CAMPAIGN_A)
    workflow_id = body["workflow_id"]

    queue = client.get("/api/content").json()
    linked = [item for item in queue if item.get("workflow_id") == workflow_id]
    assert len(linked) == 1, f"expected exactly 1 auto-created item, got {len(linked)}"
    item = linked[0]
    assert item["title"]
    assert item["content"]
    # Auto-created item starts unapproved — the human gate is preserved.
    assert item["status"] in {"Awaiting Approval", "Validation Failed"}

    # Idempotent: manual bridge on the same workflow must not duplicate.
    manual = client.post(f"/api/content/from-workflow/{workflow_id}")
    assert manual.status_code in {200, 201, 409}
    queue_after = client.get("/api/content").json()
    linked_after = [i for i in queue_after if i.get("workflow_id") == workflow_id]
    assert len(linked_after) == 1


def test_dashboard_stats_match_database():
    stats = client.get("/api/dashboard/stats").json()
    assert stats["content"]["total"] >= 1
    assert isinstance(stats["content"]["by_status"], dict)
    assert isinstance(stats["workflows"]["by_status"], dict)
    assert stats["agent_executions"]["total"] >= 7

    agent_status = client.get("/api/dashboard/agent-status").json()
    assert len(agent_status) >= 6
    for info in agent_status.values():
        assert info["status"] in {"COMPLETED", "FAILED", "RUNNING", "QUEUED", "SKIPPED", "WAITING_FOR_APPROVAL"}


def test_approval_gate_and_duplicate_schedule_detail():
    body = _run_campaign(CAMPAIGN_B)
    workflow_id = body["workflow_id"]
    queue = client.get("/api/content").json()
    item = next(i for i in queue if i.get("workflow_id") == workflow_id)

    # Unapproved content cannot be scheduled.
    early = client.post(f"/api/content/{item['id']}/schedule", json={"scheduled_for": "2031-02-01T10:00:00Z"})
    assert early.status_code == 400

    client.post(f"/api/content/{item['id']}/approve", json={"approved_by": "reviewer", "notes": "ok"})
    first = client.post(f"/api/content/{item['id']}/schedule", json={"scheduled_for": "2031-02-01T10:00:00Z"})
    assert first.status_code == 200

    # Duplicate schedule identifies the item and its scheduled time.
    duplicate = client.post(f"/api/content/{item['id']}/schedule", json={"scheduled_for": "2031-02-02T10:00:00Z"})
    assert duplicate.status_code == 409
    assert f"#{item['id']}" in duplicate.json()["detail"]
    assert "already has a scheduled job" in duplicate.json()["detail"]
