"""Outline models (ERD V1.2 §12).

Hierarchy: section -> paragraph -> sentence_idea (parent_id self-FK).
Only draft outlines are editable; confirming locks the outline. The outline
never writes into the essay body — ghost-text insertion is user-initiated.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
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

OUTLINE_STATUSES = ("generating", "draft", "confirmed", "archived", "failed")
NODE_TYPES = ("section", "paragraph", "sentence_idea")


class WritingOutline(Base):
    __tablename__ = "writing_outlines"
    __table_args__ = (
        CheckConstraint(
            "status IN ('generating', 'draft', 'confirmed', 'archived', 'failed')",
            name="ck_writing_outlines_status",
        ),
        ForeignKeyConstraint(
            ["essay_id", "user_id"],
            ["essays.id", "essays.user_id"],
            name="fk_writing_outlines_same_owner",
        ),
        UniqueConstraint("essay_id", "version_no", name="uq_writing_outlines_essay_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    essay_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("essays.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="generating")
    thesis_statement: Mapped[str | None] = mapped_column(Text)
    source_context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflows.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    nodes: Mapped[list["OutlineNode"]] = relationship(
        back_populates="outline",
        cascade="all, delete-orphan",
        order_by="OutlineNode.sort_order",
        lazy="selectin",
    )


class OutlineNode(Base):
    __tablename__ = "outline_nodes"
    __table_args__ = (
        CheckConstraint(
            "node_type IN ('section', 'paragraph', 'sentence_idea')",
            name="ck_outline_nodes_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    outline_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("writing_outlines.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("outline_nodes.id", ondelete="CASCADE")
    )
    node_type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    event_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)

    outline: Mapped[WritingOutline] = relationship(back_populates="nodes")
