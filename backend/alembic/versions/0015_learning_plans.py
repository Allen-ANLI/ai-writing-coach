"""learning plans + tasks: learning_plans, learning_tasks

Stage 2 Slice 9. Implements ERD V1.2 §13. Additive; does not modify 0001-0014.

Notes:
- learning_tasks.related_expression_id uses a composite FK to enforce the
  same-owner rule (ERD §13); related_question_id points at the system-wide
  published IELTS bank (no owner constraint).
- Task status: pending / in_progress / completed / cancelled. Plan status:
  active / paused / completed / archived.

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-15

"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learning_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("daily_target_minutes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'paused', 'completed', 'archived')",
            name="ck_learning_plans_status",
        ),
        sa.CheckConstraint(
            "daily_target_minutes IS NULL OR daily_target_minutes > 0",
            name="ck_learning_plans_daily_target",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_learning_plans_user_created",
        "learning_plans",
        ["user_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "learning_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("task_type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("related_expression_id", sa.Uuid(), nullable=True),
        sa.Column("related_question_id", sa.Uuid(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("metadata", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "task_type IN ('review', 'practice', 'writing')",
            name="ck_learning_tasks_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'cancelled')",
            name="ck_learning_tasks_status",
        ),
        sa.ForeignKeyConstraint(["plan_id"], ["learning_plans.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["related_question_id"], ["ielts_questions.id"]),
        sa.ForeignKeyConstraint(
            ["related_expression_id", "user_id"],
            ["user_expressions.id", "user_expressions.user_id"],
            name="fk_learning_tasks_expression_same_owner",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_learning_tasks_user_status", "learning_tasks", ["user_id", "status"])
    op.create_index("ix_learning_tasks_plan", "learning_tasks", ["plan_id"])


def downgrade() -> None:
    op.drop_index("ix_learning_tasks_plan", table_name="learning_tasks")
    op.drop_index("ix_learning_tasks_user_status", table_name="learning_tasks")
    op.drop_table("learning_tasks")
    op.drop_index("ix_learning_plans_user_created", table_name="learning_plans")
    op.drop_table("learning_plans")
