"""Concurrent refresh: row locks + state checks must yield exactly one winner.

The loser presents a consumed token and triggers strict reuse detection
(family + session revocation). Frontends avoid this with single-flight refresh.
"""

import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from helpers import refresh, refresh_cookie_value, register

from app.core.config import get_settings
from app.modules.auth.models import AuthRefreshToken, AuthSession


def test_concurrent_refresh_single_winner(client, db, session_factory):
    registered = register(client)
    cookie = refresh_cookie_value(registered)
    barrier = threading.Barrier(2, timeout=30)

    def attempt(_):
        # Independent client per thread; explicit cookie avoids jar races.
        with TestClient(client.app, base_url="https://testserver") as worker:
            barrier.wait()
            response = worker.post(
                "/api/v1/auth/refresh",
                cookies={get_settings().refresh_cookie_name: cookie},
            )
            return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))

    statuses = sorted(status for status, _ in results)
    assert statuses == [200, 401], results
    loser = next(body for status, body in results if status == 401)
    assert loser["error"]["code"] == "REFRESH_TOKEN_REUSE_DETECTED"

    db.expire_all()
    session = db.query(AuthSession).one()
    assert session.revoked_at is not None
    assert all(t.revoked_at is not None for t in db.query(AuthRefreshToken).all())


def test_sequential_refresh_chain_stays_consistent(client, db):
    register(client)
    for _ in range(5):
        assert refresh(client).status_code == 200

    db.expire_all()
    tokens = db.query(AuthRefreshToken).all()
    active = [t for t in tokens if t.used_at is None and t.revoked_at is None]
    assert len(active) == 1
    assert db.query(AuthSession).count() == 1
