"""CORS whitelist behavior: only documented methods/headers and local origins."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import health as health_module
from app.core.config import Settings
from app.infrastructure.database import get_db
from app.main import create_app

ALLOWED_ORIGIN = "http://localhost:3500"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(
        "app.main.get_settings",
        lambda: Settings(_env_file=None, cors_origins=[ALLOWED_ORIGIN]),
    )
    monkeypatch.setattr(health_module, "check_database_connection", lambda session: None)
    application = create_app()
    application.dependency_overrides[get_db] = lambda: MagicMock()
    return TestClient(application)


def _preflight(client, method="GET", headers=None, origin=ALLOWED_ORIGIN):
    request_headers = {"Origin": origin, "Access-Control-Request-Method": method}
    if headers is not None:
        request_headers["Access-Control-Request-Headers"] = headers
    return client.options("/api/v1/health", headers=request_headers)


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE"])
def test_preflight_allows_contract_methods(client, method):
    response = _preflight(client, method)

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert method in response.headers["access-control-allow-methods"]


def test_preflight_rejects_method_outside_whitelist(client):
    response = _preflight(client, "TRACE")

    # Starlette rejects with 400 + reason; the echoed whitelist must not
    # contain the requested method. Browsers fail any non-2xx preflight.
    assert response.status_code == 400
    assert response.text == "Disallowed CORS method"
    assert "TRACE" not in response.headers.get("access-control-allow-methods", "")


def test_preflight_allows_documented_headers(client):
    response = _preflight(client, "POST", headers="content-type, authorization, idempotency-key")

    assert response.status_code == 200
    allowed = response.headers["access-control-allow-headers"].lower()
    for header in ("content-type", "authorization", "idempotency-key"):
        assert header in allowed


def test_preflight_rejects_undocumented_header(client):
    response = _preflight(client, "GET", headers="x-custom-header")

    assert response.status_code == 400


def test_preflight_rejects_foreign_origin(client):
    response = _preflight(client, "GET", origin="http://evil.example.com")

    assert response.status_code == 400


def test_actual_get_carries_cors_headers(client):
    response = client.get("/api/v1/health", headers={"Origin": ALLOWED_ORIGIN})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
