from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowContext:
    workflow_id: str | None = None
    creator_id: int | None = None
    campaign_topic: str = ""
    target_audience: str = "general audience"
    platforms: list[str] = field(default_factory=list)
    campaign_objective: str = "content growth"
    content_type: str = "short-form"
    brand_voice: dict[str, Any] = field(default_factory=dict)
    research_findings: dict[str, Any] = field(default_factory=dict)
    competitor_findings: dict[str, Any] = field(default_factory=dict)
    hooks: list[str] = field(default_factory=list)
    creative_output: dict[str, Any] = field(default_factory=dict)
    video_output: dict[str, Any] = field(default_factory=dict)
    validation_result: dict[str, Any] = field(default_factory=dict)
    approval_status: str = "PENDING"
    scheduling: dict[str, Any] = field(default_factory=dict)
    agent_records: dict[str, dict[str, Any]] = field(default_factory=dict)
    error_message: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "WorkflowContext":
        if not isinstance(data, dict):
            return cls()

        context = cls(
            workflow_id=data.get("workflow_id"),
            creator_id=data.get("creator_id"),
            campaign_topic=data.get("campaign_topic", ""),
            target_audience=data.get("target_audience", "general audience"),
            platforms=list(data.get("platforms") or []),
            campaign_objective=data.get("campaign_objective", "content growth"),
            content_type=data.get("content_type", "short-form"),
            brand_voice=dict(data.get("brand_voice") or {}),
            research_findings=dict(data.get("research_findings") or {}),
            competitor_findings=dict(data.get("competitor_findings") or {}),
            hooks=list(data.get("hooks") or []),
            creative_output=dict(data.get("creative_output") or {}),
            video_output=dict(data.get("video_output") or {}),
            validation_result=dict(data.get("validation_result") or {}),
            approval_status=data.get("approval_status", "PENDING"),
            scheduling=dict(data.get("scheduling") or {}),
            agent_records=dict(data.get("agent_records") or {}),
            error_message=data.get("error_message"),
        )
        return context

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "creator_id": self.creator_id,
            "campaign_topic": self.campaign_topic,
            "target_audience": self.target_audience,
            "platforms": self.platforms,
            "campaign_objective": self.campaign_objective,
            "content_type": self.content_type,
            "brand_voice": self.brand_voice,
            "research_findings": self.research_findings,
            "competitor_findings": self.competitor_findings,
            "hooks": self.hooks,
            "creative_output": self.creative_output,
            "video_output": self.video_output,
            "validation_result": self.validation_result,
            "approval_status": self.approval_status,
            "scheduling": self.scheduling,
            "agent_records": self.agent_records,
            "error_message": self.error_message,
        }
