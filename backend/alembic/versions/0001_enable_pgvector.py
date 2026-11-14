"""enable pgvector extension

Baseline migration. No business entities exist yet; this only ensures the
vector extension required by later embedding/RAG stages. The Docker init
script (infrastructure/postgres/init.sql) also creates it idempotently on
first container start.

Revision ID: 0001
Revises:
Create Date: 2026-11-14

"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    # Intentional no-op: once any column or index uses the vector type,
    # DROP EXTENSION would fail or cascade destructively. Removing pgvector
    # must be a deliberate manual operation, never a side effect of rollback.
    pass
