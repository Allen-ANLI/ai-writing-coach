"""writing sessions: writing_sessions + essays owner uniqueness

Stage 2 Slice 2D. Implements ERD V1.2 §6.3. Additive; does not modify
0001-0004.

Notes:
- essays gains UNIQUE(id, user_id) so writing_sessions can carry the composite
  FK (essay_id, user_id) -> essays(id, user_id): the session user must be the
  essay owner at the database level (ERD §15.1), not only in service code.
- session status enumeration adopted: active / submitted / cancelled
  (ERD does not enumerate; recorded in ERD §6.3).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-15

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_essays_id_user_id", "essays", ["id", "user_id"])

    op.create_table(
        "writing_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("essay_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("activity_type", sa.String(length=30), nullable=False),
        sa.Column("exam_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("mode IN ('assisted', 'independent')", name="ck_writing_sessions_mode"),
        sa.CheckConstraint(
            "activity_type IN ('free_writing', 'practice', 'mock_exam')",
            name="ck_writing_sessions_activity_type",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'submitted', 'cancelled')",
            name="ck_writing_sessions_status",
        ),
        sa.ForeignKeyConstraint(["essay_id"], ["essays.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["essay_id", "user_id"],
            ["essays.id", "essays.user_id"],
            name="fk_writing_sessions_same_owner",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_writing_sessions_essay_created",
        "writing_sessions",
        ["essay_id", sa.text("created_at DESC")],
    )
    op.create_index("ix_writing_sessions_user_status", "writing_sessions", ["user_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_writing_sessions_user_status", table_name="writing_sessions")
    op.drop_index("ix_writing_sessions_essay_created", table_name="writing_sessions")
    op.drop_table("writing_sessions")
    op.drop_constraint("uq_essays_id_user_id", "essays", type_="unique")
