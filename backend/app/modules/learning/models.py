"""Learning domain models (ERD V1.2 §9.4–9.5, §10)."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.infrastructure.database import Base


class ExpressionProgress(Base):
    __tablename__ = "expression_progress"
    __table_args__ = (
        CheckConstraint(
            "status IN ('collected', 'learning', 'reviewing', 'mastered', 'archived')",
            name="ck_expression_progress_status",
        ),
        CheckConstraint("correct_count >= 0", name="ck_expression_progress_correct"),
        CheckConstraint("incorrect_count >= 0", name="ck_expression_progress_incorrect"),
        CheckConstraint("review_count >= 0", name="ck_expression_progress_reviews"),
        CheckConstraint("streak_count >= 0", name="ck_expression_progress_streak"),
        UniqueConstraint("user_id", "expression_id", name="uq_expression_progress_user_expr"),
        ForeignKeyConstraint(
            ["expression_id", "user_id"],
            ["user_expressions.id", "user_expressions.user_id"],
            name="fk_expression_progress_same_owner",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    expression_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_expressions.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="learning")
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    incorrect_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    streak_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    interval_days: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, default=Decimal("0")
    )
    ease_factor: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class ExpressionReview(Base):
    __tablename__ = "expression_reviews"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    progress_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("expression_progress.id"), nullable=False
    )
    user_answer: Mapped[str | None] = mapped_column(Text)
    reference_expression: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    feedback_json: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class UserWeakness(Base):
    __tablename__ = "user_weaknesses"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "category", "sub_category", name="uq_user_weaknesses_user_cat_sub"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    sub_category: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    total_occurrences: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recent_occurrences: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trend: Mapped[str | None] = mapped_column(String(20))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
