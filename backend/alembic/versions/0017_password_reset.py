"""auth: password_reset_tokens (reconciliation R7)

Stage 2 Slice 11. Additive; does not modify 0001-0016.

Notes:
- Only the SHA-256 hash of the reset token is stored (same pattern as
  refresh tokens). Tokens are single-use with a short TTL.
- Email delivery goes through a provider abstraction; the default console
  provider logs the link for development. Real SMTP/provider activation
  requires user approval (Directive §6) before production launch.

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-15

"""

import sqlalchemy as sa

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_tokens_hash"),
    )
    op.create_index("ix_password_reset_tokens_user", "password_reset_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_password_reset_tokens_user", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
