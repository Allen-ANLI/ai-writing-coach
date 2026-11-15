"""evaluations: essay_evaluations, essay_rewrites; edit-event rewrite reference

Stage 2 Slice 7. Implements ERD V1.2 §8.1-8.2. Additive; does not modify
0001-0012 except extending the essay_edit_events event_type enumeration and
adding its rewrite_id reference.

Notes:
- essay_evaluations carries is_estimate (default true): AI bands are always
  estimates, never official scores (ERD §8.1 rule, API Spec §13).
- Composite FK (essay_id, version_id) -> essay_versions(essay_id, id) keeps
  evaluations bound to a version of the SAME essay.
- Composite FK (evaluation_id, source_version_id) -> essay_evaluations(id,
  version_id) enforces source_version_id == evaluation.version_id at the DB
  level (ERD §8.2 rule).
- Deleting an evaluation cascades its rewrites (derived artifacts); created
  ai_rewrite versions and edit events survive (rewrite_id SET NULL).

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-15

"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "essay_evaluations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("essay_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_type", sa.String(length=30), nullable=False),
        sa.Column("task_type", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="queued", nullable=False),
        sa.Column("overall_band", sa.Numeric(precision=3, scale=1), nullable=True),
        sa.Column("criteria_scores", JSONB(), nullable=True),
        sa.Column("feedback_json", JSONB(), nullable=True),
        sa.Column("is_estimate", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "evaluation_type IN ('ielts', 'general')",
            name="ck_essay_evaluations_type",
        ),
        sa.CheckConstraint(
            "task_type IN ('task1', 'task2')", name="ck_essay_evaluations_task_type"
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed', 'cancelled')",
            name="ck_essay_evaluations_status",
        ),
        sa.ForeignKeyConstraint(["essay_id"], ["essays.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["essay_id", "version_id"],
            ["essay_versions.essay_id", "essay_versions.id"],
            name="fk_essay_evaluations_version_same_essay",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "version_id", name="uq_essay_evaluations_id_version"),
    )
    op.create_index(
        "ix_essay_evaluations_essay_created",
        "essay_evaluations",
        ["essay_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "essay_rewrites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("source_version_id", sa.Uuid(), nullable=False),
        sa.Column("result_version_id", sa.Uuid(), nullable=True),
        sa.Column("modification_level", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="queued", nullable=False),
        sa.Column("result_content_json", JSONB(), nullable=True),
        sa.Column("result_plain_text", sa.Text(), nullable=True),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "modification_level IN ('level_1', 'level_2', 'level_3', 'level_4')",
            name="ck_essay_rewrites_level",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed', 'cancelled')",
            name="ck_essay_rewrites_status",
        ),
        sa.ForeignKeyConstraint(["evaluation_id"], ["essay_evaluations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_version_id"], ["essay_versions.id"]),
        sa.ForeignKeyConstraint(["result_version_id"], ["essay_versions.id"]),
        sa.ForeignKeyConstraint(
            ["evaluation_id", "source_version_id"],
            ["essay_evaluations.id", "essay_evaluations.version_id"],
            name="fk_essay_rewrites_source_matches_evaluation",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_essay_rewrites_evaluation", "essay_rewrites", ["evaluation_id"])

    op.add_column("essay_edit_events", sa.Column("rewrite_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_essay_edit_events_rewrite",
        "essay_edit_events",
        "essay_rewrites",
        ["rewrite_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint("ck_essay_edit_events_event_type", "essay_edit_events", type_="check")
    op.create_check_constraint(
        "ck_essay_edit_events_event_type",
        "essay_edit_events",
        "event_type IN ('accept_suggestion', 'manual_revision', 'ignore_suggestion', "
        "'restore', 'submit', 'accept_rewrite')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_essay_edit_events_event_type", "essay_edit_events", type_="check")
    op.create_check_constraint(
        "ck_essay_edit_events_event_type",
        "essay_edit_events",
        "event_type IN ('accept_suggestion', 'manual_revision', 'ignore_suggestion', "
        "'restore', 'submit')",
    )
    op.drop_constraint("fk_essay_edit_events_rewrite", "essay_edit_events", type_="foreignkey")
    op.drop_column("essay_edit_events", "rewrite_id")
    op.drop_index("ix_essay_rewrites_evaluation", table_name="essay_rewrites")
    op.drop_table("essay_rewrites")
    op.drop_index("ix_essay_evaluations_essay_created", table_name="essay_evaluations")
    op.drop_table("essay_evaluations")
