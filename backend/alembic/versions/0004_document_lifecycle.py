"""document lifecycle: essay_edit_events, essay_versions.label, idempotency_keys

Stage 2 Slice 2B. Additive only; does not modify 0001/0002/0003.

Notes:
- essay_edit_events implements ERD V1.2 §6.5. issue_id / suggestion_id are plain
  UUID columns for now: their FK targets (writing_issues, issue_suggestions)
  belong to the Grammar slice and will be attached by that migration.
- essay_versions.label reconciles the contract's SnapshotCreate.label with the
  ERD (traceability matrix R3); ERD §6.4 updated accordingly.
- idempotency_keys backs the contract's Idempotency-Key header for important
  write operations (API Spec §2). response_status NULL marks an in-flight
  request; stale placeholders are reclaimed by the service layer.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-15

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "essay_versions",
        sa.Column("label", sa.String(length=255), nullable=True),
    )

    op.create_table(
        "essay_edit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("essay_id", sa.Uuid(), nullable=False),
        sa.Column("from_version_id", sa.Uuid(), nullable=True),
        sa.Column("to_version_id", sa.Uuid(), nullable=True),
        sa.Column("from_server_revision", sa.BigInteger(), nullable=True),
        sa.Column("to_server_revision", sa.BigInteger(), nullable=True),
        sa.Column("issue_id", sa.Uuid(), nullable=True),
        sa.Column("suggestion_id", sa.Uuid(), nullable=True),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("before_text", sa.Text(), nullable=True),
        sa.Column("after_text", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "actor_type IN ('user', 'ai_accept', 'system')",
            name="ck_essay_edit_events_actor_type",
        ),
        sa.CheckConstraint(
            "event_type IN ('accept_suggestion', 'manual_revision', 'ignore_suggestion', "
            "'restore', 'submit')",
            name="ck_essay_edit_events_event_type",
        ),
        sa.ForeignKeyConstraint(["essay_id"], ["essays.id"]),
        sa.ForeignKeyConstraint(
            ["essay_id", "from_version_id"],
            ["essay_versions.essay_id", "essay_versions.id"],
            name="fk_essay_edit_events_from_version_same_essay",
        ),
        sa.ForeignKeyConstraint(
            ["essay_id", "to_version_id"],
            ["essay_versions.essay_id", "essay_versions.id"],
            name="fk_essay_edit_events_to_version_same_essay",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_essay_edit_events_essay_created",
        "essay_edit_events",
        ["essay_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "idempotency_keys",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=200), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id", "key"),
    )


def downgrade() -> None:
    op.drop_table("idempotency_keys")
    op.drop_index("ix_essay_edit_events_essay_created", table_name="essay_edit_events")
    op.drop_table("essay_edit_events")
    op.drop_column("essay_versions", "label")
