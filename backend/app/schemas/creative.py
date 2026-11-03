from __future__ import annotations

from pydantic import BaseModel, Field


class CreativeRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=120)
    platform: str = Field(default="Instagram")
    content: str | None = None
    creator_image_path: str | None = None
    script: str | None = None
    captions: list[str] = Field(default_factory=list)


class CreativeResponse(BaseModel):
    status: str
    platform: str
    generated_file: str | None = None
    preview_url: str | None = None
    video_path: str | None = None
    thumbnail_path: str | None = None
    subtitle_path: str | None = None
    limits: str
