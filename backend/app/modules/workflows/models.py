"""Workflow persistence (SD §9, API Spec §15).

Business state lives in PostgreSQL so pause/resume survives restarts; the
LangGraph run itself uses in-process checkpointing. The API exposes only
business status and append-only events — never graph internals.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.infrastructure.database import Base

WORKFLOW_TYPES = ("writing_planner", "learning_extractor", "personalized_study_planner")
WORKFLOW_STATUSES = ("running", "awaiting_confirmation", "completed", "failed", "cancelled")


class Workflow(Base):
    __tablename__ = "workflows"
    __table_args__ = (
        CheckConstraint(
            "workflow_type IN ('writing_planner', 'learning_extractor', "
            "'personalized_study_planner')",
            name="ck_workflows_type",
        ),
        CheckConstraint(
            "status IN ('running', 'awaiting_confirmation', 'completed', 'failed', 'cancelled')",
            name="ck_workflows_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    workflow_type: Mapped[str] = mapped_column(String(40), nullable=False)
    essay_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("essays.id"))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running")
    input_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result_json: Mapped[dict | None] = mapped_column(JSONB)
    current_step: Mapped[str | None] = mapped_column(String(50))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    step: Mapped[str] = mapped_column(String(50), nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
