"""IELTS question bank models (ERD V1.2 §11).

Only published questions with a cleared license (``original`` or ``licensed``)
are ever exposed by the API; the gate lives in the repository layer.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.infrastructure.database import Base

TASK_TYPES = ("task1", "task2")
LICENSE_STATUSES = ("original", "licensed", "pending", "restricted")
PERMITTED_LICENSES = ("original", "licensed")
SOURCE_TYPES = ("original", "third_party")


class IeltsQuestion(Base):
    __tablename__ = "ielts_questions"
    __table_args__ = (
        CheckConstraint("task_type IN ('task1', 'task2')", name="ck_ielts_questions_task_type"),
        CheckConstraint(
            "license_status IN ('original', 'licensed', 'pending', 'restricted')",
            name="ck_ielts_questions_license_status",
        ),
        CheckConstraint(
            "source_type IN ('original', 'third_party')", name="ck_ielts_questions_source_type"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    task_type: Mapped[str] = mapped_column(String(10), nullable=False)
    question_type: Mapped[str | None] = mapped_column(String(50))
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_translation: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[str | None] = mapped_column(String(20))
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="original")
    source_title: Mapped[str | None] = mapped_column(String(255))
    source_volume: Mapped[str | None] = mapped_column(String(50))
    source_test_number: Mapped[str | None] = mapped_column(String(30))
    license_status: Mapped[str] = mapped_column(String(30), nullable=False, default="original")
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    tags: Mapped[list["QuestionTag"]] = relationship(
        secondary="ielts_question_tags", lazy="selectin", order_by="QuestionTag.name"
    )


class QuestionTag(Base):
    __tablename__ = "question_tags"
    __table_args__ = (
        UniqueConstraint("name", name="uq_question_tags_name"),
        UniqueConstraint("slug", name="uq_question_tags_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class IeltsQuestionTag(Base):
    __tablename__ = "ielts_question_tags"

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ielts_questions.id"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("question_tags.id"), primary_key=True)


class UserFavoriteQuestion(Base):
    __tablename__ = "user_favorite_questions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ielts_questions.id"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
