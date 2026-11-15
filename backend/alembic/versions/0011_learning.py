"""learning: expression_progress, expression_reviews, user_weaknesses

Stage 2 Slice 5B. Implements ERD V1.2 §9.4-9.5 and §10. Additive; does not
modify 0001-0010.

Notes:
- user_expressions gains UNIQUE(id, user_id) so expression_progress can carry
  the composite FK (expression_id, user_id) -> user_expressions(id, user_id):
  progress rows must belong to the expression owner (ERD §15.1).
- user_weaknesses.sub_category is NOT NULL DEFAULT '' so UNIQUE(user_id,
  category, sub_category) works without NULL-distinct surprises.
- Review scheduling is deterministic SM-2 style (PRD FR-05.4); no LLM decides
  intervals or mastery.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-15

"""

import sqlalchemy as sa

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_user_expressions_id_user_id", "user_expressions", ["id", "user_id"]
    )

    op.create_table(
        "expression_progress",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("expression_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="learning", nullable=False),
        sa.Column("correct_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("incorrect_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("review_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("streak_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "interval_days", sa.Numeric(precision=6, scale=2), server_default="0", nullable=False
        ),
        sa.Column("ease_factor", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('collected', 'learning', 'reviewing', 'mastered', 'archived')",
            name="ck_expression_progress_status",
        ),
        sa.CheckConstraint("correct_count >= 0", name="ck_expression_progress_correct"),
        sa.CheckConstraint("incorrect_count >= 0", name="ck_expression_progress_incorrect"),
        sa.CheckConstraint("review_count >= 0", name="ck_expression_progress_reviews"),
        sa.CheckConstraint("streak_count >= 0", name="ck_expression_progress_streak"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["expression_id"], ["user_expressions.id"]),
        sa.ForeignKeyConstraint(
            ["expression_id", "user_id"],
            ["user_expressions.id", "user_expressions.user_id"],
            name="fk_expression_progress_same_owner",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "expression_id", name="uq_expression_progress_user_expr"),
    )
    op.create_index(
        "ix_expression_progress_user_next_review",
        "expression_progress",
        ["user_id", "next_review_at"],
    )

    op.create_table(
        "expression_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("progress_id", sa.Uuid(), nullable=False),
        sa.Column("user_answer", sa.Text(), nullable=True),
        sa.Column("reference_expression", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("feedback_json", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["progress_id"], ["expression_progress.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expression_reviews_progress", "expression_reviews", ["progress_id"])

    op.create_table(
        "user_weaknesses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("sub_category", sa.String(length=80), server_default="", nullable=False),
        sa.Column("total_occurrences", sa.Integer(), server_default="0", nullable=False),
        sa.Column("recent_occurrences", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trend", sa.String(length=20), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "category", "sub_category", name="uq_user_weaknesses_user_cat_sub"
        ),
    )
    op.create_index("ix_user_weaknesses_user_category", "user_weaknesses", ["user_id", "category"])


def downgrade() -> None:
    op.drop_index("ix_user_weaknesses_user_category", table_name="user_weaknesses")
    op.drop_table("user_weaknesses")
    op.drop_index("ix_expression_reviews_progress", table_name="expression_reviews")
    op.drop_table("expression_reviews")
    op.drop_index("ix_expression_progress_user_next_review", table_name="expression_progress")
    op.drop_table("expression_progress")
    op.drop_constraint("uq_user_expressions_id_user_id", "user_expressions", type_="unique")
