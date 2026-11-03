from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    niche: str = Field(..., min_length=2, max_length=120)
    competitor_urls: list[str] = Field(default_factory=list)
    creator_writing_samples: list[str] = Field(default_factory=list)
    rss_sources: list[str] = Field(default_factory=list)


class AgentStatus(BaseModel):
    agent: str
    status: str
    started_at: str | None = None
    completed_at: str | None = None
    summary: str | None = None
    source_urls: list[str] | None = None


class ResearchResponse(BaseModel):
    workflow_id: str
    status: str
    agent_statuses: list[AgentStatus]
    ranked_topic_suggestions: list[dict[str, Any]] = Field(default_factory=list)
    competitor_observations: list[dict[str, Any]] = Field(default_factory=list)
    content_gap_suggestions: list[dict[str, Any]] = Field(default_factory=list)
    creator_style_scripts: list[dict[str, Any]] = Field(default_factory=list)
    hook_alternatives: list[str] = Field(default_factory=list)
