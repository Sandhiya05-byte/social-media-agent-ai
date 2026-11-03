import os
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

for path in [Path("test_phase4_social_agent.db"), Path("app/scheduler_jobs.db")]:
    if path.exists():
        path.unlink()

os.environ["DATABASE_URL"] = "sqlite:///./test_phase4_social_agent.db"

from app.main import app

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
    scheduled = client.post(f"/api/content/{item['id']}/schedule", json={"scheduled_for": (datetime.utcnow() + timedelta(minutes=30)).isoformat()})
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

    future = datetime.utcnow() + timedelta(minutes=45)
    scheduled = client.post(f"/api/content/{item['id']}/schedule", json={"scheduled_for": future.isoformat()})
    assert scheduled.status_code == 200
    assert scheduled.json()["status"] == "Scheduled"

    cancelled = client.post(f"/api/content/{item['id']}/cancel-schedule")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "Approved"

    rescheduled = client.post(f"/api/content/{item['id']}/reschedule", json={"scheduled_for": (datetime.utcnow() + timedelta(hours=2)).isoformat()})
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

    first_schedule = client.post(f"/api/content/{item['id']}/schedule", json={"scheduled_for": (datetime.utcnow() + timedelta(minutes=10)).isoformat()})
    assert first_schedule.status_code == 200

    second_schedule = client.post(f"/api/content/{item['id']}/schedule", json={"scheduled_for": (datetime.utcnow() + timedelta(minutes=20)).isoformat()})
    assert second_schedule.status_code == 409
    assert "already has a scheduled job" in second_schedule.json()["detail"]
