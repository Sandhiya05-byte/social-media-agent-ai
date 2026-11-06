from datetime import timedelta

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.content import ContentItem
from app.services.scheduler_service import execute_scheduled_publish
from app.time_utils import utcnow

client = TestClient(app)


def test_validation_flags_missing_fields_and_risk_language():
    payload = {
        "title": "",
        "platform": "YouTube",
        "content": "This is a guaranteed viral hack for instant growth.",
        "script": "",
        "captions": ["Hook", "CTA"],
        "media_path": "",
    }

    response = client.post("/api/content/validate", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert any("Title is required" in error for error in body["errors"])
    assert body["requires_human_review"] is True
    assert any("Potential policy or trust risk" in warning for warning in body["warnings"])


def test_content_can_be_approved_and_rejected():
    payload = {
        "title": "Creator Growth Playbook",
        "platform": "Instagram",
        "content": "A simple system to grow without chasing trends. Use clear messaging with repeatable systems.",
        "script": "Use a repeatable framework to make clear, consistent content.",
        "captions": ["Hook", "Explain", "Framework", "CTA"],
        "media_path": "/generated/creative/instagram_creator_growth_playbook.png",
    }

    created = client.post("/api/content", json=payload)
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["status"] == "Awaiting Approval"

    approved = client.post(f"/api/content/{item['id']}/approve", json={"approved_by": "creator", "notes": "Looks good."})
    assert approved.status_code == 200
    assert approved.json()["status"] == "Approved"

    rejected = client.post(f"/api/content/{item['id']}/reject", json={"notes": "Needs a stronger hook."})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "Rejected"


def test_unapproved_content_cannot_be_scheduled():
    payload = {
        "title": "Rejected content",
        "platform": "LinkedIn",
        "content": "A thoughtful insight for professionals building sustainable creator businesses.",
        "script": "Use serious, practical language for a professional audience.",
        "captions": ["We can design better systems."],
        "media_path": "/generated/creative/linkedin_insight.png",
    }

    created = client.post("/api/content", json=payload)
    item = created.json()
    scheduled = client.post(f"/api/content/{item['id']}/schedule", json={"scheduled_for": (utcnow() + timedelta(minutes=30)).isoformat()})
    assert scheduled.status_code == 400
    assert "Only approved content" in scheduled.json()["detail"]


def test_content_can_be_scheduled_cancelled_and_rescheduled():
    payload = {
        "title": "Weekly Creator Insight",
        "platform": "YouTube",
        "content": "A practical framework for building consistent creator systems without burnout.",
        "script": "Here is the process I follow to create a repeatable content engine.",
        "captions": ["Hook", "Framework", "CTA"],
        "media_path": "/generated/creative/youtube_creator_insight.png",
    }

    created = client.post("/api/content", json=payload)
    item = created.json()

    approve = client.post(f"/api/content/{item['id']}/approve", json={"approved_by": "reviewer"})
    assert approve.status_code == 200

    future = utcnow() + timedelta(minutes=45)
    scheduled = client.post(f"/api/content/{item['id']}/schedule", json={"scheduled_for": future.isoformat()})
    assert scheduled.status_code == 200
    assert scheduled.json()["status"] == "Scheduled"

    cancelled = client.post(f"/api/content/{item['id']}/cancel-schedule")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "Approved"

    rescheduled = client.post(f"/api/content/{item['id']}/reschedule", json={"scheduled_for": (utcnow() + timedelta(hours=2)).isoformat()})
    assert rescheduled.status_code == 200
    assert rescheduled.json()["status"] == "Scheduled"


def test_duplicate_scheduling_is_rejected():
    payload = {
        "title": "Duplicate Scheduling Test",
        "platform": "Instagram",
        "content": "A content idea that is already approved and should only be scheduled once.",
        "script": "A simple script for a short creator growth reel.",
        "captions": ["One clear idea", "A simple system", "CTA"],
        "media_path": "/generated/creative/instagram_duplicate_test.png",
    }

    created = client.post("/api/content", json=payload)
    item = created.json()
    client.post(f"/api/content/{item['id']}/approve", json={"approved_by": "creator"})

    first_schedule = client.post(f"/api/content/{item['id']}/schedule", json={"scheduled_for": (utcnow() + timedelta(minutes=10)).isoformat()})
    assert first_schedule.status_code == 200

    second_schedule = client.post(f"/api/content/{item['id']}/schedule", json={"scheduled_for": (utcnow() + timedelta(minutes=20)).isoformat()})
    assert second_schedule.status_code == 409
    assert "already has a scheduled job" in second_schedule.json()["detail"]


def test_scheduling_normalizes_timezone_to_utc():
    created = client.post(
        "/api/content",
        json={
            "title": "Timezone normalization test",
            "platform": "Instagram",
            "content": "A practical post used to verify UTC schedule normalization.",
            "script": "A short script for the timezone test.",
            "captions": ["One clear idea"],
        },
    )
    item = created.json()
    client.post(f"/api/content/{item['id']}/approve", json={"approved_by": "creator"})

    scheduled = client.post(
        f"/api/content/{item['id']}/schedule",
        json={"scheduled_for": "2030-01-01T12:00:00+02:00"},
    )
    assert scheduled.status_code == 200, scheduled.text
    assert scheduled.json()["scheduled_for"].startswith("2030-01-01T10:00:00")

    cancelled = client.post(f"/api/content/{item['id']}/cancel-schedule")
    assert cancelled.status_code == 200


def test_scheduler_publishes_only_scheduled_content():
    with SessionLocal() as db:
        scheduled = ContentItem(
            title="Scheduled publishing test",
            platform="Instagram",
            content="This approved content should be published by the scheduler.",
            status="Scheduled",
            scheduled_for=utcnow(),
        )
        draft = ContentItem(
            title="Draft publishing test",
            platform="Instagram",
            content="This draft must remain unpublished.",
            status="Draft",
        )
        db.add_all([scheduled, draft])
        db.commit()
        db.refresh(scheduled)
        db.refresh(draft)
        scheduled_id = scheduled.id
        draft_id = draft.id

    execute_scheduled_publish(scheduled_id)
    execute_scheduled_publish(draft_id)

    with SessionLocal() as db:
        published = db.get(ContentItem, scheduled_id)
        untouched = db.get(ContentItem, draft_id)
        assert published.status == "Published"
        assert published.published_at is not None
        assert "Local publishing simulation completed." in published.approval_notes
        assert untouched.status == "Draft"
        assert untouched.published_at is None
