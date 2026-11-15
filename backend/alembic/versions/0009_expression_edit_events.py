"""edit events: expression suggestion reference

Stage 2 Slice 4. essay_edit_events.suggestion_id references grammar
issue_suggestions (ERD §6.5); expression assistance acceptance needs its own
reference to expression_suggestion_items. Additive; does not modify 0001-0008.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-15

"""

import sqlalchemy as sa

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "essay_edit_events",
        sa.Column("expression_suggestion_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_essay_edit_events_expression_suggestion",
        "essay_edit_events",
        "expression_suggestion_items",
        ["expression_suggestion_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_essay_edit_events_expression_suggestion", "essay_edit_events", type_="foreignkey"
    )
    op.drop_column("essay_edit_events", "expression_suggestion_id")
