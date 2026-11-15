"""outlines: outline_chat_messages (conversational planner, ADR-024)

Additive; does not modify 0001-0017.

Notes:
- Chat history for the left-panel planning agent: the learner discusses the
  essay structure conversationally; proposed/revised outlines are stored as
  regular writing_outlines drafts and linked from the assistant message.
- Same-owner composite FK keeps messages scoped to the essay's owner.
- outline_id is SET NULL when an outline is deleted so history survives.

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-15

"""

import sqlalchemy as sa

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outline_chat_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("essay_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("outline_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_outline_chat_messages_role"),
        sa.ForeignKeyConstraint(["essay_id"], ["essays.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["outline_id"], ["writing_outlines.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["essay_id", "user_id"],
            ["essays.id", "essays.user_id"],
            name="fk_outline_chat_messages_same_owner",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_outline_chat_messages_essay_created",
        "outline_chat_messages",
        ["essay_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_outline_chat_messages_essay_created", table_name="outline_chat_messages")
    op.drop_table("outline_chat_messages")
