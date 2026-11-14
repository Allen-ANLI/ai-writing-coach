"""User and UserProfile models (ERD V1.2 §5.1–5.2)."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.infrastructure.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("status IN ('active', 'disabled')", name="ck_users_status"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    profile: Mapped["UserProfile"] = relationship(
        back_populates="user", uselist=False, lazy="joined"
    )


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(80))
    native_language: Mapped[str] = mapped_column(
        String(20), nullable=False, default="zh", server_default="zh"
    )
    english_level: Mapped[str | None] = mapped_column(String(30))
    target_exam: Mapped[str | None] = mapped_column(String(30))
    target_writing_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    preferred_english_variant: Mapped[str | None] = mapped_column(String(20))
    preferences: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    user: Mapped[User] = relationship(back_populates="profile")
