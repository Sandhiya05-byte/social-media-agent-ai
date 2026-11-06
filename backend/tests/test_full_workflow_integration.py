from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_all_seven_agents_complete_through_approval_and_resume():
    created = client.post(
        "/api/orchestration/workflows",
        json={
            "campaign_topic": "Creator growth systems",
            "target_audience": "new creators",
            "platforms": ["Instagram"],
            "campaign_objective": "Build clear educational content.",
            "content_type": "short-form",
            "competitor_urls": ["https://example.com/competitor"],
            "rss_sources": ["https://example.com/rss"],
            "creator_writing_samples": ["Clarity compounds. Systems are scalable."],
        },
    )
    assert created.status_code == 200, created.text
    workflow = created.json()
    workflow_id = workflow["workflow_id"]
    assert workflow["status"] in {"PENDING", "WAITING_FOR_APPROVAL"}

    status = client.get(f"/api/orchestration/workflows/{workflow_id}")
    assert status.status_code == 200
    assert status.json()["status"] == "WAITING_FOR_APPROVAL"

    approved = client.post(
        f"/api/orchestration/workflows/{workflow_id}/approve",
        json={"approved_by": "integration-test", "notes": "Approved for publishing prep."},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"

    resumed = client.post(f"/api/orchestration/workflows/{workflow_id}/resume")
    assert resumed.status_code == 200, resumed.text
    resumed_body = resumed.json()
    assert resumed_body["status"] == "COMPLETED"

    agent_records = resumed_body["context"]["agent_records"]
    expected_agents = {
        "Trend Research Agent",
        "Competitor Intelligence Agent",
        "Brand Voice Agent",
        "Hook Generation Agent",
        "AI Clone and Creative Agent",
        "Video Production Agent",
        "Publishing and Scheduling Agent",
    }
    assert set(agent_records) == expected_agents
    assert all(record["status"] == "completed" for record in agent_records.values())

    preview_url = resumed_body["context"]["creative_output"]["preview_url"]
    assert preview_url.startswith("/generated/creative/")
    preview = client.get(preview_url)
    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith("image/")

    video_output = resumed_body["context"]["video_output"]
    assert video_output["video_format"] in {"mp4", "gif"}
    assert video_output["render_engine"] in {"ffmpeg", "pillow"}
    assert resumed_body["context"]["scheduling"]["requires_explicit_approval"] is True
