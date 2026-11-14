"""Essay, EssayWorkingDocument and EssayVersion models (ERD V1.2 §6.1–6.4).

Invariants:
- Each essay has exactly one working document; autosave (later slice) increments
  server_revision and never creates versions.
- Versions are immutable snapshots; the original snapshot is never overwritten.
- essays has NO current_version_id (the working document is the live content).
- question_id FK to ielts_questions is deferred until that table exists.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.infrastructure.database import Base


class Essay(Base):
    __tablename__ = "essays"
    __table_args__ = (
        CheckConstraint(
            "writing_type IN ('free_writing', 'ielts_task1', 'ielts_task2', 'other')",
            name="ck_essays_writing_type",
        ),
        CheckConstraint("status IN ('active', 'archived')", name="ck_essays_status"),
        ForeignKeyConstraint(
            ["id", "original_version_id"],
            ["essay_versions.essay_id", "essay_versions.id"],
            name="fk_essays_original_version_same_essay",
        ),
        ForeignKeyConstraint(
            ["id", "final_version_id"],
            ["essay_versions.essay_id", "essay_versions.id"],
            name="fk_essays_final_version_same_essay",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    question_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    title: Mapped[str | None] = mapped_column(String(255))
    writing_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    original_version_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    final_version_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    working_document: Mapped["EssayWorkingDocument"] = relationship(
        back_populates="essay", uselist=False, lazy="joined"
    )


class EssayWorkingDocument(Base):
    __tablename__ = "essay_working_documents"

    essay_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("essays.id"), primary_key=True)
    content_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    plain_text: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    server_revision: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    last_saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    essay: Mapped[Essay] = relationship(back_populates="working_document")


class EssayVersion(Base):
    __tablename__ = "essay_versions"
    __table_args__ = (
        CheckConstraint(
            "version_type IN ('original', 'checkpoint', 'assisted', 'ai_rewrite', 'final')",
            name="ck_essay_versions_version_type",
        ),
        UniqueConstraint("essay_id", "version_no", name="uq_essay_versions_essay_version_no"),
        UniqueConstraint("essay_id", "id", name="uq_essay_versions_essay_id_id"),
        ForeignKeyConstraint(
            ["essay_id", "parent_version_id"],
            ["essay_versions.essay_id", "essay_versions.id"],
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    essay_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("essays.id"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    version_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    plain_text: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
