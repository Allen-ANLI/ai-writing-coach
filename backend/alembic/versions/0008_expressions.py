"""expressions: user_expressions, expression_sources, expression_suggestions

Stage 2 Slice 4. Implements ERD V1.2 §9.1-9.2 plus the expression-suggestion
persistence needed by API Spec §8 (polish/translation candidates and their
atomic acceptance). Additive; does not modify 0001-0007.

Notes:
- user_expressions.status enumeration adopted from PRD FR-04.3:
  collected / learning / reviewing / mastered / archived.
- expression_suggestions + items are an ERD extension (recorded in ERD §9.6):
  the contract's accept endpoint references suggestion ids, so candidates
  must be persisted server-side; accepted text is applied from storage.
- expression_embeddings arrives with the RAG slice (pgvector).

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-15

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_expressions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("english_text", sa.Text(), nullable=False),
        sa.Column("chinese_meaning", sa.Text(), nullable=True),
        sa.Column("original_text", sa.Text(), nullable=True),
        sa.Column("learning_value_reason", sa.Text(), nullable=True),
        sa.Column("usage_context", sa.Text(), nullable=True),
        sa.Column("topic", sa.String(length=80), nullable=True),
        sa.Column("register", sa.String(length=30), nullable=True),
        sa.Column("grammar_pattern", sa.Text(), nullable=True),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), server_default="collected", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('collected', 'learning', 'reviewing', 'mastered', 'archived')",
            name="ck_user_expressions_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_expressions_user_created",
        "user_expressions",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index("ix_user_expressions_user_status", "user_expressions", ["user_id", "status"])

    op.create_table(
        "expression_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("expression_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("essay_id", sa.Uuid(), nullable=True),
        sa.Column("essay_version_id", sa.Uuid(), nullable=True),
        sa.Column("issue_id", sa.Uuid(), nullable=True),
        sa.Column("suggestion_id", sa.Uuid(), nullable=True),
        sa.Column("source_context", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_type IN ('translation', 'correction', 'suggestion', 'essay', 'manual')",
            name="ck_expression_sources_type",
        ),
        sa.ForeignKeyConstraint(["expression_id"], ["user_expressions.id"]),
        sa.ForeignKeyConstraint(["essay_id"], ["essays.id"]),
        sa.ForeignKeyConstraint(["essay_version_id"], ["essay_versions.id"]),
        sa.ForeignKeyConstraint(["issue_id"], ["writing_issues.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expression_sources_expression", "expression_sources", ["expression_id"])

    op.create_table(
        "expression_suggestions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("essay_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("selected_text", sa.Text(), nullable=False),
        sa.Column("sentence_context", sa.Text(), nullable=False),
        sa.Column("paragraph_context", sa.Text(), nullable=True),
        sa.Column("server_revision", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('polish', 'translation')", name="ck_expression_suggestions_kind"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'dismissed')",
            name="ck_expression_suggestions_status",
        ),
        sa.ForeignKeyConstraint(["essay_id"], ["essays.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_expression_suggestions_essay", "expression_suggestions", ["essay_id", "status"]
    )

    op.create_table(
        "expression_suggestion_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("suggestion_id", sa.Uuid(), nullable=False),
        sa.Column("english_text", sa.Text(), nullable=False),
        sa.Column("chinese_meaning", sa.Text(), nullable=True),
        sa.Column("usage_note", sa.Text(), nullable=True),
        sa.Column("register", sa.String(length=30), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("expression_id", sa.Uuid(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source IN ('llm', 'previously_learned')",
            name="ck_expression_suggestion_items_source",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'dismissed')",
            name="ck_expression_suggestion_items_status",
        ),
        sa.ForeignKeyConstraint(["suggestion_id"], ["expression_suggestions.id"]),
        sa.ForeignKeyConstraint(["expression_id"], ["user_expressions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_expression_suggestion_items_suggestion",
        "expression_suggestion_items",
        ["suggestion_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_expression_suggestion_items_suggestion", table_name="expression_suggestion_items"
    )
    op.drop_table("expression_suggestion_items")
    op.drop_index("ix_expression_suggestions_essay", table_name="expression_suggestions")
    op.drop_table("expression_suggestions")
    op.drop_index("ix_expression_sources_expression", table_name="expression_sources")
    op.drop_table("expression_sources")
    op.drop_index("ix_user_expressions_user_status", table_name="user_expressions")
    op.drop_index("ix_user_expressions_user_created", table_name="user_expressions")
    op.drop_table("user_expressions")
