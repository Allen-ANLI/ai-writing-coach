"""Health endpoint smoke tests with a mocked database probe (no PostgreSQL needed)."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.v1 import health as health_module
from app.infrastructure.database import get_db
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    application = create_app()
    application.dependency_overrides[get_db] = lambda: MagicMock()
    return TestClient(application)


def test_health_returns_200_when_database_reachable(client, monkeypatch):
    monkeypatch.setattr(health_module, "check_database_connection", lambda session: None)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == {"status": "ok", "database": "connected"}
    assert isinstance(body["meta"]["request_id"], str)


def test_health_returns_503_envelope_when_database_unreachable(client, monkeypatch):
    def fail(session):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr(health_module, "check_database_connection", fail)

    response = client.get("/api/v1/health")

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert body["error"]["message"] == "Database is not reachable."
    assert isinstance(body["meta"]["request_id"], str)
    assert "data" not in body


def test_health_does_not_require_authentication(client, monkeypatch):
    monkeypatch.setattr(health_module, "check_database_connection", lambda session: None)

    response = client.get("/api/v1/health", headers={})

    assert response.status_code == 200
