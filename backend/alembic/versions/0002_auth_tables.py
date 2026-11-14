"""auth tables: users, user_profiles, auth_sessions, auth_refresh_tokens

Stage 2 Slice 1. Implements ERD V1.2 §5.1–5.4 only; no other business tables.
Does not modify migration 0001.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-14

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('active', 'disabled')", name="ck_users_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=True),
        sa.Column("native_language", sa.String(length=20), server_default="zh", nullable=False),
        sa.Column("english_level", sa.String(length=30), nullable=True),
        sa.Column("target_exam", sa.String(length=30), nullable=True),
        sa.Column("target_writing_score", sa.Numeric(precision=3, scale=1), nullable=True),
        sa.Column("preferred_english_variant", sa.String(length=20), nullable=True),
        sa.Column(
            "preferences",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("device_label", sa.String(length=120), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auth_sessions_user_created",
        "auth_sessions",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index("ix_auth_sessions_user_revoked", "auth_sessions", ["user_id", "revoked_at"])
    op.create_table(
        "auth_refresh_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("token_family_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_token_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["auth_sessions.id"]),
        sa.ForeignKeyConstraint(["replaced_by_token_id"], ["auth_refresh_tokens.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_auth_refresh_tokens_token_hash"),
    )
    op.create_index("ix_auth_refresh_tokens_session", "auth_refresh_tokens", ["session_id"])
    op.create_index("ix_auth_refresh_tokens_family", "auth_refresh_tokens", ["token_family_id"])
    # ERD: at most one valid unconsumed token per session at any time.
    op.create_index(
        "uq_auth_refresh_tokens_active_session",
        "auth_refresh_tokens",
        ["session_id"],
        unique=True,
        postgresql_where=sa.text("used_at IS NULL AND revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_auth_refresh_tokens_active_session", table_name="auth_refresh_tokens")
    op.drop_index("ix_auth_refresh_tokens_family", table_name="auth_refresh_tokens")
    op.drop_index("ix_auth_refresh_tokens_session", table_name="auth_refresh_tokens")
    op.drop_table("auth_refresh_tokens")
    op.drop_index("ix_auth_sessions_user_revoked", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_created", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("user_profiles")
    op.drop_table("users")
