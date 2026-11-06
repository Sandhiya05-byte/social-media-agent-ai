from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.time_utils import utcnow


class ContentItem(Base):
    __tablename__ = "content_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workflow_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    creator_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    platform: Mapped[str] = mapped_column(String(40), default="Instagram", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    script: Mapped[str | None] = mapped_column(Text, nullable=True)
    captions: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="Draft", nullable=False)
    validation_errors: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    validation_warnings: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    approval_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    generation_source: Mapped[str | None] = mapped_column(String(60), nullable=True)
    source_references: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
