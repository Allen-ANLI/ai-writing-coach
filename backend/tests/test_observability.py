"""Observability & hardening tests (Slice 11b): request tracing, structured
logging, general rate limiting."""

import logging

from app.core import rate_limit
from app.core.config import get_settings


def test_request_id_header_and_echo(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")

    echoed = client.get("/api/v1/health", headers={"X-Request-ID": "trace-abc-123"})
    assert echoed.headers["X-Request-ID"] == "trace-abc-123"


def test_access_log_is_structured(client, caplog):
    # Health checks are logged at DEBUG to avoid production noise.
    with caplog.at_level(logging.DEBUG, logger="awc.request"):
        client.get("/api/v1/health", headers={"X-Request-ID": "trace-log-1"})
    record = next(r for r in caplog.records if getattr(r, "request_id", None) == "trace-log-1")
    assert record.method == "GET"
    assert record.path == "/api/v1/health"
    assert record.status == 200
    assert isinstance(record.duration_ms, float)


def test_general_rate_limit_blocks_after_limit(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "api_rate_limit_max_requests", 3)
    monkeypatch.setattr(settings, "api_rate_limit_window_seconds", 60)
    rate_limit.reset_rate_limiter()
    try:
        assert rate_limit.check_general_rate_limit("203.0.113.9") is True
        assert rate_limit.check_general_rate_limit("203.0.113.9") is True
        assert rate_limit.check_general_rate_limit("203.0.113.9") is True
        assert rate_limit.check_general_rate_limit("203.0.113.9") is False
        # A different IP is unaffected.
        assert rate_limit.check_general_rate_limit("203.0.113.10") is True
    finally:
        rate_limit.reset_rate_limiter()


def test_general_rate_limit_disabled_when_zero(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "api_rate_limit_max_requests", 0)
    rate_limit.reset_rate_limiter()
    for _ in range(50):
        assert rate_limit.check_general_rate_limit("203.0.113.11") is True
