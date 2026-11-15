"""expressions: suggestion item offsets (ADR-026 fragment-level polish)

Additive; does not modify 0001-0018. Nullable: legacy selection-based
suggestions have no fragment offsets; sentence-polish items store the
absolute unicode_codepoint range of the unnatural fragment they replace.

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-15

"""

import sqlalchemy as sa

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "expression_suggestion_items", sa.Column("start_offset", sa.Integer(), nullable=True)
    )
    op.add_column(
        "expression_suggestion_items", sa.Column("end_offset", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("expression_suggestion_items", "end_offset")
    op.drop_column("expression_suggestion_items", "start_offset")
