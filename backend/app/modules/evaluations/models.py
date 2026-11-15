"""Evaluation and rewrite models (ERD V1.2 §8.1–8.2).

Invariants:
- Evaluations bind an IMMUTABLE version of the same essay (composite FK).
- AI bands are estimates (is_estimate always true for AI results).
- A rewrite's source_version_id equals its evaluation's version_id
  (composite FK); acceptance creates an ai_rewrite version and never
  overwrites the Original snapshot.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.infrastructure.database import Base

EVALUATION_STATUSES = ("queued", "processing", "completed", "failed", "cancelled")
MODIFICATION_LEVELS = ("level_1", "level_2", "level_3", "level_4")


class EssayEvaluation(Base):
    __tablename__ = "essay_evaluations"
    __table_args__ = (
        CheckConstraint(
            "evaluation_type IN ('ielts', 'general')", name="ck_essay_evaluations_type"
        ),
        CheckConstraint("task_type IN ('task1', 'task2')", name="ck_essay_evaluations_task_type"),
        CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed', 'cancelled')",
            name="ck_essay_evaluations_status",
        ),
        ForeignKeyConstraint(
            ["essay_id", "version_id"],
            ["essay_versions.essay_id", "essay_versions.id"],
            name="fk_essay_evaluations_version_same_essay",
        ),
        UniqueConstraint("id", "version_id", name="uq_essay_evaluations_id_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    essay_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("essays.id"), nullable=False)
    version_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    evaluation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    task_type: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    overall_band: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    criteria_scores: Mapped[dict | None] = mapped_column(JSONB)
    feedback_json: Mapped[dict | None] = mapped_column(JSONB)
    is_estimate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    model_name: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class EssayRewrite(Base):
    __tablename__ = "essay_rewrites"
    __table_args__ = (
        CheckConstraint(
            "modification_level IN ('level_1', 'level_2', 'level_3', 'level_4')",
            name="ck_essay_rewrites_level",
        ),
        CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed', 'cancelled')",
            name="ck_essay_rewrites_status",
        ),
        ForeignKeyConstraint(
            ["evaluation_id", "source_version_id"],
            ["essay_evaluations.id", "essay_evaluations.version_id"],
            name="fk_essay_rewrites_source_matches_evaluation",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("essay_evaluations.id", ondelete="CASCADE"), nullable=False
    )
    source_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("essay_versions.id"), nullable=False
    )
    result_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("essay_versions.id"))
    modification_level: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    result_content_json: Mapped[dict | None] = mapped_column(JSONB)
    result_plain_text: Mapped[str | None] = mapped_column(Text)
    change_summary: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
