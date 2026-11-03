from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent


class PublishingSchedulingAgent(BaseAgent):
    name = "Publishing and Scheduling Agent"

    def execute(self, campaign_topic: str, platforms: list[str] | None = None, status: str = "PENDING", **kwargs) -> dict[str, Any]:
        self.status = "running"
        platform_list = platforms or ["Instagram"]
        schedule = {
            "campaign_topic": campaign_topic,
            "platforms": platform_list,
            "status": status,
            "published": False,
            "requires_explicit_approval": True,
            "safe_local_mode": True,
            "limitations": "No live platform publishing is configured without official API access and permissions.",
        }
        self.status = "completed"
        return {
            "agent": self.name,
            "status": self.status,
            "started_at": self._now(),
            "completed_at": self._now(),
            "schedule": schedule,
            "summary": f"Scheduling plan prepared for {campaign_topic} with explicit approval gates.",
        }
