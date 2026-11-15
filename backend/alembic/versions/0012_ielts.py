"""ielts: question bank, tags, favorites; essays.question_id FK; original seed

Stage 2 Slice 6. Implements ERD V1.2 §11. Additive; does not modify 0001-0011
except attaching the deferred essays.question_id foreign key.

Notes:
- Only published questions with license_status in ('original','licensed') are
  exposed by the API (repository gate). The seed is 100% original content
  written for this product (PRD FR-08 / reconciliation R12); no third-party
  material is reproduced.
- Seed rows use deterministic uuid5 ids so re-running is idempotent. The seed
  lives in app.modules.ielts.seed; keep existing keys stable forever.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-15

"""

import sqlalchemy as sa
from sqlalchemy.orm import Session

from alembic import context, op
from app.modules.ielts.seed import seed_ielts

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ielts_questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("task_type", sa.String(length=10), nullable=False),
        sa.Column("question_type", sa.String(length=50), nullable=True),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("prompt_translation", sa.Text(), nullable=True),
        sa.Column("difficulty", sa.String(length=20), nullable=True),
        sa.Column("source_type", sa.String(length=30), server_default="original", nullable=False),
        sa.Column("source_title", sa.String(length=255), nullable=True),
        sa.Column("source_volume", sa.String(length=50), nullable=True),
        sa.Column("source_test_number", sa.String(length=30), nullable=True),
        sa.Column(
            "license_status", sa.String(length=30), server_default="original", nullable=False
        ),
        sa.Column("is_published", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("task_type IN ('task1', 'task2')", name="ck_ielts_questions_task_type"),
        sa.CheckConstraint(
            "license_status IN ('original', 'licensed', 'pending', 'restricted')",
            name="ck_ielts_questions_license_status",
        ),
        sa.CheckConstraint(
            "source_type IN ('original', 'third_party')", name="ck_ielts_questions_source_type"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ielts_questions_published_task",
        "ielts_questions",
        ["is_published", "task_type"],
    )

    op.create_table(
        "question_tags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_question_tags_name"),
        sa.UniqueConstraint("slug", name="uq_question_tags_slug"),
    )

    op.create_table(
        "ielts_question_tags",
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["ielts_questions.id"]),
        sa.ForeignKeyConstraint(["tag_id"], ["question_tags.id"]),
        sa.PrimaryKeyConstraint("question_id", "tag_id"),
    )

    op.create_table(
        "user_favorite_questions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["question_id"], ["ielts_questions.id"]),
        sa.PrimaryKeyConstraint("user_id", "question_id"),
    )
    op.create_index(
        "ix_user_favorite_questions_question", "user_favorite_questions", ["question_id"]
    )

    op.create_foreign_key(
        "fk_essays_question_id", "essays", "ielts_questions", ["question_id"], ["id"]
    )

    # Seeding needs a live connection; offline --sql mode emits DDL only.
    if not context.is_offline_mode():
        bind = op.get_bind()
        with Session(bind=bind) as session:
            seed_ielts(session)
            session.commit()


def downgrade() -> None:
    op.drop_constraint("fk_essays_question_id", "essays", type_="foreignkey")
    op.drop_index("ix_user_favorite_questions_question", table_name="user_favorite_questions")
    op.drop_table("user_favorite_questions")
    op.drop_table("ielts_question_tags")
    op.drop_table("question_tags")
    op.drop_index("ix_ielts_questions_published_task", table_name="ielts_questions")
    op.drop_table("ielts_questions")
