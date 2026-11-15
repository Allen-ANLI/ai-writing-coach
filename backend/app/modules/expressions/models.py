"""Expression domain models (ERD V1.2 §9.1–9.2 + §9.6 suggestion extension)."""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.infrastructure.database import Base


class UserExpression(Base):
    __tablename__ = "user_expressions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('collected', 'learning', 'reviewing', 'mastered', 'archived')",
            name="ck_user_expressions_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    english_text: Mapped[str] = mapped_column(Text, nullable=False)
    chinese_meaning: Mapped[str | None] = mapped_column(Text)
    original_text: Mapped[str | None] = mapped_column(Text)
    learning_value_reason: Mapped[str | None] = mapped_column(Text)
    usage_context: Mapped[str | None] = mapped_column(Text)
    topic: Mapped[str | None] = mapped_column(String(80))
    register: Mapped[str | None] = mapped_column(String(30))
    grammar_pattern: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="collected")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sources: Mapped[list["ExpressionSource"]] = relationship(back_populates="expression")


class ExpressionSource(Base):
    __tablename__ = "expression_sources"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('translation', 'correction', 'suggestion', 'essay', 'manual')",
            name="ck_expression_sources_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    expression_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_expressions.id"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    essay_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("essays.id"))
    essay_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("essay_versions.id"))
    issue_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("writing_issues.id"))
    suggestion_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    source_context: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    expression: Mapped[UserExpression] = relationship(back_populates="sources")


class ExpressionSuggestion(Base):
    """A polish/translation request's candidate set (ERD §9.6 extension)."""

    __tablename__ = "expression_suggestions"
    __table_args__ = (
        CheckConstraint("kind IN ('polish', 'translation')", name="ck_expression_suggestions_kind"),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'dismissed')",
            name="ck_expression_suggestions_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    essay_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("essays.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    selected_text: Mapped[str] = mapped_column(Text, nullable=False)
    sentence_context: Mapped[str] = mapped_column(Text, nullable=False)
    paragraph_context: Mapped[str | None] = mapped_column(Text)
    server_revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    items: Mapped[list["ExpressionSuggestionItem"]] = relationship(
        back_populates="suggestion", order_by="ExpressionSuggestionItem.sort_order"
    )


class ExpressionSuggestionItem(Base):
    __tablename__ = "expression_suggestion_items"
    __table_args__ = (
        CheckConstraint(
            "source IN ('llm', 'previously_learned')",
            name="ck_expression_suggestion_items_source",
        ),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'dismissed')",
            name="ck_expression_suggestion_items_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    suggestion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("expression_suggestions.id"), nullable=False
    )
    english_text: Mapped[str] = mapped_column(Text, nullable=False)
    chinese_meaning: Mapped[str | None] = mapped_column(Text)
    usage_note: Mapped[str | None] = mapped_column(Text)
    register: Mapped[str | None] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    expression_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_expressions.id"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # ADR-026: absolute unicode_codepoint range of the fragment this option
    # replaces (sentence-polish only; legacy selection items have NULL).
    start_offset: Mapped[int | None] = mapped_column(Integer)
    end_offset: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    suggestion: Mapped[ExpressionSuggestion] = relationship(back_populates="items")


class ExpressionEmbedding(Base):
    """Rebuildable semantic vector (ERD §9.3). Model + content hash identify
    stale embeddings when the provider or text changes."""

    __tablename__ = "expression_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "expression_id",
            "embedding_model",
            "content_hash",
            name="uq_expression_embeddings_expr_model_hash",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    expression_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_expressions.id"), nullable=False
    )
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding_version: Mapped[str | None] = mapped_column(String(50))
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(VECTOR(1536), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
