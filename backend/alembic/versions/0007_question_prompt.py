"""essay question prompt + grammar suggestion acceptance support

Stage 2 Slice 3UX (user decision 2026-11-15 §2.1): the essay question is shown
in a separate, non-editable section of the editor. essays gains a nullable
question_prompt snapshot for display; question_id remains the future link to
the IELTS bank (FK still deferred until ielts_questions exists).

Additive; does not modify 0001-0006.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-15

"""

import sqlalchemy as sa

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("essays", sa.Column("question_prompt", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("essays", "question_prompt")
