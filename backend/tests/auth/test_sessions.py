"""Session listing, revocation, logout, logout-all, ownership isolation."""

import uuid

import jwt
from helpers import auth_header, login, refresh, refresh_cookie_value, register

from app.modules.auth.models import AuthSession


def _sid(response) -> uuid.UUID:
    token = response.json()["data"]["access_token"]
    return uuid.UUID(jwt.decode(token, options={"verify_signature": False})["sid"])


def test_list_sessions_marks_current(client):
    first = register(client)
    second = login(client)

    response = client.get("/api/v1/auth/sessions", headers=auth_header(second))

    assert response.status_code == 200
    items = response.json()["data"]
    assert len(items) == 2
    current = [s for s in items if s["is_current"]]
    assert len(current) == 1
    assert current[0]["id"] == str(_sid(second))
    assert str(_sid(first)) in [s["id"] for s in items]


def test_list_sessions_serializes_inet_ip_as_string(client, db):
    # Regression: psycopg returns INET as ipaddress objects; the API must
    # emit a string. TestClient stores NULL IPs, so set one explicitly.
    registered = register(client)
    session = db.get(AuthSession, _sid(registered))
    session.ip_address = "127.0.0.1"
    db.commit()

    response = client.get("/api/v1/auth/sessions", headers=auth_header(registered))

    assert response.status_code == 200
    assert response.json()["data"][0]["ip_address"] == "127.0.0.1"


def test_revoke_session_blocks_refresh_and_access(client):
    registered = register(client)
    cookie = refresh_cookie_value(registered)
    session_id = _sid(registered)

    revoked = client.delete(f"/api/v1/auth/sessions/{session_id}", headers=auth_header(registered))
    assert revoked.status_code == 204

    assert refresh(client, cookie_value=cookie).status_code == 401
    assert client.get("/api/v1/users/me", headers=auth_header(registered)).status_code == 401


def test_revoke_foreign_session_returns_404(client):
    register(client, email="a@example.com")
    victim = register(client, email="b@example.com")
    attacker = login(client, email="a@example.com")

    response = client.delete(f"/api/v1/auth/sessions/{_sid(victim)}", headers=auth_header(attacker))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_revoke_already_revoked_session_returns_404(client):
    registered = register(client)
    session_id = _sid(registered)
    headers = auth_header(registered)
    assert client.delete(f"/api/v1/auth/sessions/{session_id}", headers=headers).status_code == 204

    # The revoked session's own access token is dead; use a fresh login.
    fresh = login(client)
    again = client.delete(f"/api/v1/auth/sessions/{session_id}", headers=auth_header(fresh))

    assert again.status_code == 404


def test_logout_revokes_current_session_and_clears_cookie(client, db):
    registered = register(client)
    other = login(client)

    response = client.post("/api/v1/auth/logout", headers=auth_header(registered))

    assert response.status_code == 204
    set_cookie = response.headers.get("set-cookie", "")
    assert "awc_refresh_token=" in set_cookie
    assert "Max-Age=0" in set_cookie or "expires=" in set_cookie.lower()
    db.expire_all()
    sessions = {s.id: s for s in db.query(AuthSession).all()}
    assert sessions[_sid(registered)].revoked_at is not None
    assert sessions[_sid(other)].revoked_at is None
    # The other device keeps working.
    assert client.get("/api/v1/users/me", headers=auth_header(other)).status_code == 200


def test_logout_all_revokes_every_session_of_user_only(client, db):
    a1 = register(client, email="a@example.com")
    a2 = login(client, email="a@example.com")
    b1 = register(client, email="b@example.com")
    b_cookie = refresh_cookie_value(b1)

    response = client.post("/api/v1/auth/logout-all", headers=auth_header(a1))

    assert response.status_code == 200
    assert response.json()["data"]["revoked_sessions"] == 2
    db.expire_all()
    a_user_id = _sid_user(a1)
    assert all(
        s.revoked_at is not None for s in db.query(AuthSession).all() if s.user_id == a_user_id
    )
    listed = client.get("/api/v1/auth/sessions", headers=auth_header(a2))
    assert listed.status_code == 401
    # User B is untouched.
    assert client.get("/api/v1/users/me", headers=auth_header(b1)).status_code == 200
    assert refresh(client, cookie_value=b_cookie).status_code == 200


def _sid_user(response) -> uuid.UUID:
    token = response.json()["data"]["access_token"]
    return uuid.UUID(jwt.decode(token, options={"verify_signature": False})["sub"])
