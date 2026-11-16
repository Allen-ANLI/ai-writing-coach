"""outlines: sentence-aligned Chinese translation + markdown outline (ADR-032)

Additive; does not modify 0001-0020. model_essay reverts to the ENGLISH source
essay; model_essay_zh is its sentence-by-sentence Chinese translation (1:1 with
English sentences, drives ghost hints); outline_md is a clean markdown rendering
of the outline for readable display. Nullable for legacy outlines.

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-16

"""

import sqlalchemy as sa

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("writing_outlines", sa.Column("model_essay_zh", sa.Text(), nullable=True))
    op.add_column("writing_outlines", sa.Column("outline_md", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("writing_outlines", "outline_md")
    op.drop_column("writing_outlines", "model_essay_zh")