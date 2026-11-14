"""Cookie attributes, CSRF origin checks, rate limiting, no token leakage."""

from helpers import PASSWORD, login, refresh, refresh_cookie_value, register

from app.core.config import Settings


def test_refresh_cookie_attributes(client):
    response = register(client)

    set_cookie = response.headers["set-cookie"]
    assert "awc_refresh_token=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "samesite=strict" in set_cookie.lower()
    assert "Path=/api/v1/auth" in set_cookie
    assert "Max-Age=2592000" in set_cookie


def test_refresh_token_never_in_json_body(client):
    registered = register(client)
    cookie = refresh_cookie_value(registered)
    assert cookie not in registered.text

    logged_in = login(client)
    assert refresh_cookie_value(logged_in) not in logged_in.text

    rotated = refresh(client)
    assert refresh_cookie_value(rotated) not in rotated.text
    assert rotated.json()["data"]["token_type"] == "bearer"


def test_csrf_foreign_origin_blocked(client):
    register(client)

    response = refresh(client, origin="http://evil.example.com")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "RESOURCE_ACCESS_DENIED"


def test_csrf_allowed_origin_passes(client):
    register(client)

    response = refresh(client, origin="http://localhost:3500")

    assert response.status_code == 200


def test_csrf_absent_origin_allowed_for_non_browser_clients(client):
    register(client)

    response = refresh(client)

    assert response.status_code == 200


def test_register_rate_limited(client, monkeypatch):
    monkeypatch.setattr(
        "app.core.rate_limit.get_settings",
        lambda: Settings(
            _env_file=None, auth_rate_limit_max_requests=2, auth_rate_limit_window_seconds=300
        ),
    )

    assert register(client, email="one@example.com").status_code == 201
    assert register(client, email="two@example.com").status_code == 201
    limited = register(client, email="three@example.com")

    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


def test_login_rate_limited(client, monkeypatch):
    register(client)
    monkeypatch.setattr(
        "app.core.rate_limit.get_settings",
        lambda: Settings(
            _env_file=None, auth_rate_limit_max_requests=1, auth_rate_limit_window_seconds=300
        ),
    )

    assert login(client).status_code == 200
    limited = login(client, password=PASSWORD)

    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
