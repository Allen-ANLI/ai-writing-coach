"""outlines: model essay for ghost guidance (ADR-029)

Additive; does not modify 0001-0019. Nullable: outlines created before
ADR-029 (and workflow-generated outlines) have no model essay; ghost
guidance falls back to the flattened outline ideas for those.

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-16

"""

import sqlalchemy as sa

from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("writing_outlines", sa.Column("model_essay", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("writing_outlines", "model_essay")