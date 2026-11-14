-- Runs once on first container initialization (empty data volume).
-- Alembic migration 0001 also ensures this extension idempotently.
CREATE EXTENSION IF NOT EXISTS vector;
