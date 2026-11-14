"""grammar domain: writing_issues, issue_suggestions, issue_teachings, ai_usage_logs

Stage 2 Slice 3. Implements ERD V1.2 §7.1-7.3 and §14. Additive; does not
modify 0001-0005. Attaches the deferred essay_edit_events issue/suggestion FKs.

Notes:
- writing_issues binds source_server_revision; essay_version_id is nullable
  until an exact-revision snapshot archives the issue (ERD §15.2). The
  source_revision equality is enforced in the service layer (a FK cannot
  express it).
- issue_teachings stores only contextual explanations (ADR-015): no generic
  teaching library.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-15

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "writing_issues",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("essay_id", sa.Uuid(), nullable=False),
        sa.Column("essay_version_id", sa.Uuid(), nullable=True),
        sa.Column("source_server_revision", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("sub_category", sa.String(length=80), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("rule_id", sa.String(length=100), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("offset_unit", sa.String(length=30), nullable=False),
        sa.Column("anchor_text", sa.Text(), nullable=False),
        sa.Column("prefix_context", sa.Text(), nullable=True),
        sa.Column("suffix_context", sa.Text(), nullable=True),
        sa.Column("short_explanation", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="detected", nullable=False),
        sa.Column("resolved_by_server_revision", sa.BigInteger(), nullable=True),
        sa.Column("resolved_by_version_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("start_offset >= 0", name="ck_writing_issues_start_offset"),
        sa.CheckConstraint("end_offset > start_offset", name="ck_writing_issues_end_offset"),
        sa.CheckConstraint("source_server_revision >= 1", name="ck_writing_issues_source_revision"),
        sa.CheckConstraint(
            "source IN ('rule_engine', 'llm', 'hybrid')", name="ck_writing_issues_source"
        ),
        sa.CheckConstraint(
            "severity IN ('high', 'medium', 'low')", name="ck_writing_issues_severity"
        ),
        sa.CheckConstraint(
            "status IN ('detected', 'resolved', 'ignored', 'stale')",
            name="ck_writing_issues_status",
        ),
        sa.CheckConstraint(
            "offset_unit = 'unicode_codepoint'", name="ck_writing_issues_offset_unit"
        ),
        sa.ForeignKeyConstraint(["essay_id"], ["essays.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["essay_id", "essay_version_id"],
            ["essay_versions.essay_id", "essay_versions.id"],
            name="fk_writing_issues_version_same_essay",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_writing_issues_essay_revision",
        "writing_issues",
        ["essay_id", "source_server_revision"],
    )
    op.create_index(
        "ix_writing_issues_essay_version", "writing_issues", ["essay_id", "essay_version_id"]
    )
    op.create_index(
        "ix_writing_issues_user_category",
        "writing_issues",
        ["user_id", "category", sa.text("created_at DESC")],
    )
    op.create_index("ix_writing_issues_essay_status", "writing_issues", ["essay_id", "status"])

    op.create_table(
        "issue_suggestions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("issue_id", sa.Uuid(), nullable=False),
        sa.Column("suggested_text", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_recommended", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("source IN ('rule_engine', 'llm')", name="ck_issue_suggestions_source"),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'dismissed')",
            name="ck_issue_suggestions_status",
        ),
        sa.ForeignKeyConstraint(["issue_id"], ["writing_issues.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_issue_suggestions_issue", "issue_suggestions", ["issue_id"])

    op.create_table(
        "issue_teachings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("issue_id", sa.Uuid(), nullable=False),
        sa.Column("essay_version_id", sa.Uuid(), nullable=True),
        sa.Column("source_server_revision", sa.BigInteger(), nullable=False),
        sa.Column("context_hash", sa.String(length=64), nullable=False),
        sa.Column("context_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("explanation_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["issue_id"], ["writing_issues.id"]),
        sa.ForeignKeyConstraint(["essay_version_id"], ["essay_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_issue_teachings_issue", "issue_teachings", ["issue_id"])

    op.create_table(
        "ai_usage_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("feature", sa.String(length=50), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("trace_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_usage_logs_user_created",
        "ai_usage_logs",
        ["user_id", sa.text("created_at DESC")],
    )

    op.create_foreign_key(
        "fk_essay_edit_events_issue", "essay_edit_events", "writing_issues", ["issue_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_essay_edit_events_suggestion",
        "essay_edit_events",
        "issue_suggestions",
        ["suggestion_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_essay_edit_events_suggestion", "essay_edit_events", type_="foreignkey")
    op.drop_constraint("fk_essay_edit_events_issue", "essay_edit_events", type_="foreignkey")
    op.drop_index("ix_ai_usage_logs_user_created", table_name="ai_usage_logs")
    op.drop_table("ai_usage_logs")
    op.drop_index("ix_issue_teachings_issue", table_name="issue_teachings")
    op.drop_table("issue_teachings")
    op.drop_index("ix_issue_suggestions_issue", table_name="issue_suggestions")
    op.drop_table("issue_suggestions")
    op.drop_index("ix_writing_issues_essay_status", table_name="writing_issues")
    op.drop_index("ix_writing_issues_user_category", table_name="writing_issues")
    op.drop_index("ix_writing_issues_essay_version", table_name="writing_issues")
    op.drop_index("ix_writing_issues_essay_revision", table_name="writing_issues")
    op.drop_table("writing_issues")
