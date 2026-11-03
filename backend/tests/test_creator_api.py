import os
from pathlib import Path

from fastapi.testclient import TestClient

test_db_path = Path("test_social_agent.db")
if test_db_path.exists():
    test_db_path.unlink()

os.environ["DATABASE_URL"] = "sqlite:///./test_social_agent.db"

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_and_get_creator():
    payload = {
        "name": "Alicia Moreno",
        "brand_name": "Alicia Creates",
        "niche": "creator growth",
        "email": "hello@aliciacreates.com",
        "platform_focus": "Instagram",
        "bio": "Marketing educator for creators.",
        "website": "https://aliciacreates.com",
        "approved_for_publication": True,
        "authorized_for_avatar_use": False,
    }

    create_response = client.post("/api/creators", json=payload)
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    assert created["brand_name"] == "Alicia Creates"

    get_response = client.get(f"/api/creators/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["email"] == payload["email"]
