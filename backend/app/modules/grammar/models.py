"""Grammar domain models (ERD V1.2 §7.1–7.3)."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.infrastructure.database import Base


class WritingIssue(Base):
    __tablename__ = "writing_issues"
    __table_args__ = (
        CheckConstraint("start_offset >= 0", name="ck_writing_issues_start_offset"),
        CheckConstraint("end_offset > start_offset", name="ck_writing_issues_end_offset"),
        CheckConstraint("source_server_revision >= 1", name="ck_writing_issues_source_revision"),
        CheckConstraint(
            "source IN ('rule_engine', 'llm', 'hybrid')", name="ck_writing_issues_source"
        ),
        CheckConstraint("severity IN ('high', 'medium', 'low')", name="ck_writing_issues_severity"),
        CheckConstraint(
            "status IN ('detected', 'resolved', 'ignored', 'stale')",
            name="ck_writing_issues_status",
        ),
        CheckConstraint("offset_unit = 'unicode_codepoint'", name="ck_writing_issues_offset_unit"),
        ForeignKeyConstraint(
            ["essay_id", "essay_version_id"],
            ["essay_versions.essay_id", "essay_versions.id"],
            name="fk_writing_issues_version_same_essay",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    essay_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("essays.id"), nullable=False)
    essay_version_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    source_server_revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    sub_category: Mapped[str | None] = mapped_column(String(80))
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    rule_id: Mapped[str | None] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    offset_unit: Mapped[str] = mapped_column(
        String(30), nullable=False, default="unicode_codepoint"
    )
    anchor_text: Mapped[str] = mapped_column(Text, nullable=False)
    prefix_context: Mapped[str | None] = mapped_column(Text)
    suffix_context: Mapped[str | None] = mapped_column(Text)
    short_explanation: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="detected")
    resolved_by_server_revision: Mapped[int | None] = mapped_column(BigInteger)
    resolved_by_version_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    suggestions: Mapped[list["IssueSuggestion"]] = relationship(
        back_populates="issue", order_by="IssueSuggestion.sort_order"
    )


class IssueSuggestion(Base):
    __tablename__ = "issue_suggestions"
    __table_args__ = (
        CheckConstraint("source IN ('rule_engine', 'llm')", name="ck_issue_suggestions_source"),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'dismissed')",
            name="ck_issue_suggestions_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    issue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("writing_issues.id"), nullable=False)
    suggested_text: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    is_recommended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    issue: Mapped[WritingIssue] = relationship(back_populates="suggestions")


class IssueTeaching(Base):
    """Contextual teaching only (ADR-015): cached per user+issue+revision+
    context_hash; never a generic reusable teaching library."""

    __tablename__ = "issue_teachings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    issue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("writing_issues.id"), nullable=False)
    essay_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("essay_versions.id"))
    source_server_revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    context_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    explanation_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
