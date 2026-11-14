"""AuthSession and AuthRefreshToken models (ERD V1.2 §5.3–5.4).

A session is a stable device login; refresh tokens are individual rotation
records. Rotation never creates a new session. Only token hashes are stored.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.infrastructure.database import Base


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        Index("ix_auth_sessions_user_created", "user_id", text("created_at DESC")),
        Index("ix_auth_sessions_user_revoked", "user_id", "revoked_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    device_label: Mapped[str | None] = mapped_column(String(120))
    user_agent: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(INET)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    refresh_tokens: Mapped[list["AuthRefreshToken"]] = relationship(back_populates="session")


class AuthRefreshToken(Base):
    __tablename__ = "auth_refresh_tokens"
    __table_args__ = (
        Index("ix_auth_refresh_tokens_session", "session_id"),
        Index("ix_auth_refresh_tokens_family", "token_family_id"),
        # ERD: at most one valid unconsumed token per session at any time.
        Index(
            "uq_auth_refresh_tokens_active_session",
            "session_id",
            unique=True,
            postgresql_where=text("used_at IS NULL AND revoked_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("auth_sessions.id"), nullable=False)
    token_family_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_token_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("auth_refresh_tokens.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    session: Mapped[AuthSession] = relationship(back_populates="refresh_tokens")
