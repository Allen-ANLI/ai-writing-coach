"""Real PostgreSQL integration checks.

Skipped automatically when the database is unreachable. To run them:
    docker compose up -d db
    (from backend/) alembic upgrade head
    pytest
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.infrastructure.database import engine
from app.main import create_app


def _database_reachable() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _database_reachable(),
    reason="PostgreSQL is not reachable; start it with 'docker compose up -d db'",
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_health_reports_real_database_connection(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["data"] == {"status": "ok", "database": "connected"}


def test_pgvector_extension_is_enabled():
    with engine.connect() as connection:
        version = connection.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar_one_or_none()

    assert version is not None
