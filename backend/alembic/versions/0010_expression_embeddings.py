"""expression embeddings: pgvector semantic retrieval (ERD §9.3)

Stage 2 Slice 5A. Additive; does not modify 0001-0009.

Notes:
- VECTOR(1536) matches EMBEDDING_DIMENSIONS default; a different embedding
  dimension requires a coordinated migration + config change (documented).
- Embeddings are rebuildable: UNIQUE(expression_id, embedding_model,
  content_hash) lets re-embedding detect stale vectors.
- HNSW cosine index for user-scoped semantic recall.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-15

"""

import sqlalchemy as sa
from pgvector.sqlalchemy import VECTOR

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "expression_embeddings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("expression_id", sa.Uuid(), nullable=False),
        sa.Column("embedding_model", sa.String(length=100), nullable=False),
        sa.Column("embedding_version", sa.String(length=50), nullable=True),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding", VECTOR(1536), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["expression_id"], ["user_expressions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "expression_id",
            "embedding_model",
            "content_hash",
            name="uq_expression_embeddings_expr_model_hash",
        ),
    )
    op.create_index(
        "ix_expression_embeddings_expression",
        "expression_embeddings",
        ["expression_id"],
    )
    op.execute(
        "CREATE INDEX ix_expression_embeddings_hnsw ON expression_embeddings "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_index("ix_expression_embeddings_hnsw", table_name="expression_embeddings")
    op.drop_index("ix_expression_embeddings_expression", table_name="expression_embeddings")
    op.drop_table("expression_embeddings")
