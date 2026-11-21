"""outlines: per-sentence model-essay annotations (ADR-037)

Additive; does not modify 0001-0021. model_essay_annotations stores the
expressions + sentence pattern extracted for EACH model_essay sentence at
generation time (1:1, same order), shown alongside the matching ghost hint.
Nullable for legacy outlines and when alignment validation drops the output.

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-21

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "writing_outlines",
        sa.Column("model_essay_annotations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("writing_outlines", "model_essay_annotations")