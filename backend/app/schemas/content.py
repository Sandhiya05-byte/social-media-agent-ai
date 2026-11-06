from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ContentValidationRequest(BaseModel):
    title: str = Field(..., max_length=180)
    platform: str = Field(default="Instagram")
    content: str = Field(..., max_length=5000)
    script: str | None = Field(default=None, max_length=6000)
    captions: list[str] = Field(default_factory=list)
    media_path: str | None = None


class ContentCreate(ContentValidationRequest):
    status: str | None = None


class ContentApprovalRequest(BaseModel):
    approved_by: str | None = None
    notes: str | None = None


class ScheduleRequest(BaseModel):
    scheduled_for: datetime


class ValidationResult(BaseModel):
    status: str
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    requires_human_review: bool = False
    platform_checks: list[str] = Field(default_factory=list)


class ContentRead(BaseModel):
    id: int
    title: str
    platform: str
    content: str
    script: str | None = None
    captions: list[str] = Field(default_factory=list)
    media_path: str | None = None
    status: str
    validation_errors: list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)
    approval_notes: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    scheduled_for: datetime | None = None
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    workflow_id: int | None = None
    generation_source: str | None = None
    media_url: str | None = None
    thumbnail_url: str | None = None
    subtitle_url: str | None = None

    model_config = ConfigDict(from_attributes=True)
