from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.services.content_validation import PLATFORM_REQUIREMENTS


class PublishingSchedulingAgent(BaseAgent):
    name = "Publishing and Scheduling Agent"

    def execute(
        self,
        campaign_topic: str,
        platforms: list[str] | None = None,
        status: str = "PENDING",
        **kwargs,
    ) -> dict[str, Any]:
        self.status = "running"
        started_at = self._now()
        platform_list = platforms or ["Instagram"]
        creative = kwargs.get("creative_output") or {}

        # Platform requirement checks against the generated creative output.
        requirements_met: dict[str, list[str]] = {}
        unmet: list[str] = []
        for platform in platform_list:
            met, missing = [], []
            for description, check in PLATFORM_REQUIREMENTS.get(platform, []):
                try:
                    (met if check(creative) else missing).append(description)
                except Exception:
                    missing.append(description)
            requirements_met[platform] = met
            unmet.extend(f"{platform}: {item}" for item in missing)

        schedule = {
            "campaign_topic": campaign_topic,
            "platforms": platform_list,
            "status": status,
            "published": False,
            "requires_explicit_approval": True,
            "safe_local_mode": True,
            "platform_requirements_met": requirements_met,
            "platform_requirements_unmet": unmet,
            "limitations": (
                "No live platform publishing is configured without official API access and permissions. "
                "Scheduling is local-only until platform credentials are configured."
            ),
        }
        self.status = "completed"
        return {
            "agent": self.name,
            "status": self.status,
            "started_at": started_at,
            "completed_at": self._now(),
            "schedule": schedule,
            "summary": (
                f"Scheduling plan prepared for {campaign_topic} with explicit approval gates. "
                f"Requirements met: {sum(len(v) for v in requirements_met.values())}, unmet: {len(unmet)}."
            ),
        }
