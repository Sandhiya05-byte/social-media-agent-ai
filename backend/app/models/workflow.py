from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.time_utils import utcnow


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    creator_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    campaign_topic: Mapped[str] = mapped_column(String(200), nullable=False)
    target_audience: Mapped[str] = mapped_column(String(200), nullable=False, default="general audience")
    platforms: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    campaign_objective: Mapped[str] = mapped_column(String(250), nullable=False, default="content growth")
    content_type: Mapped[str] = mapped_column(String(120), nullable=False, default="short-form")
    status: Mapped[str] = mapped_column(String(40), default="CREATED", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    execution_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    checkpoint_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    last_successful_agent: Mapped[str | None] = mapped_column(String(160), nullable=True)
    last_checkpoint_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approval_status: Mapped[str] = mapped_column(String(40), default="PENDING", nullable=False)
    approval_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approval_content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    content_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    executions: Mapped[list["AgentExecution"]] = relationship(back_populates="workflow")


class AgentExecution(Base):
    __tablename__ = "agent_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id"), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="PENDING", nullable=False)
    input_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    output_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    execution_duration: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    workflow: Mapped[Workflow] = relationship(back_populates="executions")
