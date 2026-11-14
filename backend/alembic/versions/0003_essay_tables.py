"""essay tables: essays, essay_working_documents, essay_versions

Stage 2 Slice 2A. Implements ERD V1.2 §6.1–6.4 only. Does not modify 0001/0002.

Notes:
- essays.question_id is a plain UUID column for now: the ERD foreign key targets
  ielts_questions, which belongs to a later slice and must not be created here.
  The FK will be added by the migration that introduces ielts_questions.
- Composite foreign keys (ERD §15.1) guarantee that original/final versions and
  version parents belong to the same essay.
- essays.status uses a provisional CHECK set ('active','archived'); the ERD does
  not enumerate values yet (flagged for approval in the slice report).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-14

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "essays",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("writing_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("original_version_id", sa.Uuid(), nullable=True),
        sa.Column("final_version_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "writing_type IN ('free_writing', 'ielts_task1', 'ielts_task2', 'other')",
            name="ck_essays_writing_type",
        ),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_essays_status"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_essays_user_updated", "essays", ["user_id", sa.text("updated_at DESC")])

    op.create_table(
        "essay_working_documents",
        sa.Column("essay_id", sa.Uuid(), nullable=False),
        sa.Column("content_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("plain_text", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("server_revision", sa.BigInteger(), server_default="1", nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("last_saved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["essay_id"], ["essays.id"]),
        sa.PrimaryKeyConstraint("essay_id"),
    )

    op.create_table(
        "essay_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("essay_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("version_type", sa.String(length=20), nullable=False),
        sa.Column("content_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("plain_text", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("source_revision", sa.BigInteger(), nullable=False),
        sa.Column("parent_version_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "version_type IN ('original', 'checkpoint', 'assisted', 'ai_rewrite', 'final')",
            name="ck_essay_versions_version_type",
        ),
        sa.ForeignKeyConstraint(["essay_id"], ["essays.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["essay_id", "parent_version_id"],
            ["essay_versions.essay_id", "essay_versions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("essay_id", "version_no", name="uq_essay_versions_essay_version_no"),
        sa.UniqueConstraint("essay_id", "id", name="uq_essay_versions_essay_id_id"),
    )
    op.create_index(
        "ix_essay_versions_essay_created",
        "essay_versions",
        ["essay_id", sa.text("created_at DESC")],
    )

    # Same-essay ownership of the essay's version pointers (ERD §15.1).
    op.create_foreign_key(
        "fk_essays_original_version_same_essay",
        "essays",
        "essay_versions",
        ["id", "original_version_id"],
        ["essay_id", "id"],
    )
    op.create_foreign_key(
        "fk_essays_final_version_same_essay",
        "essays",
        "essay_versions",
        ["id", "final_version_id"],
        ["essay_id", "id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_essays_final_version_same_essay", "essays", type_="foreignkey")
    op.drop_constraint("fk_essays_original_version_same_essay", "essays", type_="foreignkey")
    op.drop_index("ix_essay_versions_essay_created", table_name="essay_versions")
    op.drop_table("essay_versions")
    op.drop_table("essay_working_documents")
    op.drop_index("ix_essays_user_updated", table_name="essays")
    op.drop_table("essays")
