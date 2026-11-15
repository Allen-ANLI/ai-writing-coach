"""outlines + workflows: writing_outlines, outline_nodes, workflows, workflow_events

Stage 2 Slice 8. Implements ERD V1.2 §12 and the SD §9 workflow persistence
(business state in PostgreSQL; graph-level checkpointing is in-process).
Additive; does not modify 0001-0013.

Notes:
- writing_outlines.status: generating / draft / confirmed / archived / failed.
  Only draft outlines are editable; confirm locks the outline.
- outline_nodes is a hierarchy (section -> paragraph -> sentence_idea) via
  parent_id self-FK with cascade delete.
- workflows expose business status only (never graph internals); events are
  append-only for the polling UI.
- Same-owner composite FKs keep outlines bound to the essay owner.

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-15

"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_type", sa.String(length=40), nullable=False),
        sa.Column("essay_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="running", nullable=False),
        sa.Column("input_json", JSONB(), nullable=False),
        sa.Column("result_json", JSONB(), nullable=True),
        sa.Column("current_step", sa.String(length=50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "workflow_type IN ('writing_planner', 'learning_extractor', "
            "'personalized_study_planner')",
            name="ck_workflows_type",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'awaiting_confirmation', 'completed', 'failed', 'cancelled')",
            name="ck_workflows_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["essay_id"], ["essays.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workflows_user_created", "workflows", ["user_id", sa.text("created_at DESC")]
    )

    op.create_table(
        "writing_outlines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("essay_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="generating", nullable=False),
        sa.Column("thesis_statement", sa.Text(), nullable=True),
        sa.Column("source_context", JSONB(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('generating', 'draft', 'confirmed', 'archived', 'failed')",
            name="ck_writing_outlines_status",
        ),
        sa.ForeignKeyConstraint(["essay_id"], ["essays.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["essay_id", "user_id"],
            ["essays.id", "essays.user_id"],
            name="fk_writing_outlines_same_owner",
        ),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("essay_id", "version_no", name="uq_writing_outlines_essay_version"),
    )
    op.create_index("ix_writing_outlines_essay", "writing_outlines", ["essay_id"])

    op.create_table(
        "outline_nodes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("outline_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("node_type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("metadata", JSONB(), nullable=False),
        sa.CheckConstraint(
            "node_type IN ('section', 'paragraph', 'sentence_idea')",
            name="ck_outline_nodes_type",
        ),
        sa.ForeignKeyConstraint(["outline_id"], ["writing_outlines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["outline_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outline_nodes_outline_sort", "outline_nodes", ["outline_id", "sort_order"])

    op.create_table(
        "workflow_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("step", sa.String(length=50), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("payload_json", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workflow_events_workflow_created",
        "workflow_events",
        ["workflow_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_events_workflow_created", table_name="workflow_events")
    op.drop_table("workflow_events")
    op.drop_index("ix_outline_nodes_outline_sort", table_name="outline_nodes")
    op.drop_table("outline_nodes")
    op.drop_index("ix_writing_outlines_essay", table_name="writing_outlines")
    op.drop_table("writing_outlines")
    op.drop_index("ix_workflows_user_created", table_name="workflows")
    op.drop_table("workflows")
