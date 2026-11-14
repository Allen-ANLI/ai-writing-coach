"""Writing session model (ERD V1.2 §6.3).

Two writing modes only (assisted / independent); exam conditions are a
configuration of independent mode, never a third mode. The composite FK
(essay_id, user_id) -> essays(id, user_id) enforces same-owner at the DB level.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.infrastructure.database import Base


class WritingSession(Base):
    __tablename__ = "writing_sessions"
    __table_args__ = (
        CheckConstraint("mode IN ('assisted', 'independent')", name="ck_writing_sessions_mode"),
        CheckConstraint(
            "activity_type IN ('free_writing', 'practice', 'mock_exam')",
            name="ck_writing_sessions_activity_type",
        ),
        CheckConstraint(
            "status IN ('active', 'submitted', 'cancelled')",
            name="ck_writing_sessions_status",
        ),
        ForeignKeyConstraint(
            ["essay_id", "user_id"],
            ["essays.id", "essays.user_id"],
            name="fk_writing_sessions_same_owner",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    essay_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("essays.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    exam_config: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
