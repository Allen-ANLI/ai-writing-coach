"""Refresh rotation: same session, family tracking, reuse detection."""

from datetime import timedelta

import jwt
from helpers import auth_header, refresh, refresh_cookie_value, register

from app.core.time import utcnow
from app.modules.auth.models import AuthRefreshToken, AuthSession


def _sid(response) -> str:
    token = response.json()["data"]["access_token"]
    return jwt.decode(token, options={"verify_signature": False})["sid"]


def test_refresh_rotates_within_same_session_and_family(client, db):
    registered = register(client)
    old_cookie = refresh_cookie_value(registered)
    old_token = db.query(AuthRefreshToken).one()

    response = refresh(client)

    assert response.status_code == 200
    new_cookie = refresh_cookie_value(response)
    assert new_cookie and new_cookie != old_cookie
    assert _sid(response) == _sid(registered)
    assert db.query(AuthSession).count() == 1

    db.expire_all()
    old = db.get(AuthRefreshToken, old_token.id)
    assert old.used_at is not None
    assert old.replaced_by_token_id is not None
    new = db.get(AuthRefreshToken, old.replaced_by_token_id)
    assert new.token_family_id == old.token_family_id
    assert new.session_id == old.session_id
    assert new.used_at is None
    # The plaintext refresh token never appears in the JSON body.
    assert new_cookie not in response.text
    assert old_cookie not in response.text


def test_refresh_missing_cookie_rejected(client):
    response = client.post("/api/v1/auth/refresh")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_refresh_unknown_token_rejected(client):
    response = refresh(client, cookie_value="unknown-token-value")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_reuse_of_consumed_token_revokes_family_and_session(client, db):
    registered = register(client)
    old_cookie = refresh_cookie_value(registered)
    rotated = refresh(client)
    assert rotated.status_code == 200
    new_cookie = refresh_cookie_value(rotated)

    reused = refresh(client, cookie_value=old_cookie)

    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "REFRESH_TOKEN_REUSE_DETECTED"

    db.expire_all()
    session = db.query(AuthSession).one()
    assert session.revoked_at is not None
    tokens = db.query(AuthRefreshToken).all()
    assert len(tokens) == 2
    assert all(t.revoked_at is not None for t in tokens)

    # The winner's replacement token is dead too (strict family revocation).
    after = refresh(client, cookie_value=new_cookie)
    assert after.status_code == 401
    assert after.json()["error"]["code"] == "REFRESH_TOKEN_REVOKED"


def test_refresh_expired_token_rejected(client, db):
    register(client)
    token = db.query(AuthRefreshToken).one()
    token.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()

    response = refresh(client)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_refresh_after_logout_rejected(client):
    registered = register(client)
    cookie = refresh_cookie_value(registered)
    logged_out = client.post("/api/v1/auth/logout", headers=auth_header(registered))
    assert logged_out.status_code == 204

    # Logout clears the cookie; present the old value explicitly to verify
    # the revoked-token semantics rather than the missing-cookie path.
    response = refresh(client, cookie_value=cookie)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "REFRESH_TOKEN_REVOKED"


def test_refresh_updates_last_used_at(client, db):
    register(client)
    before = db.query(AuthSession).one().last_used_at

    assert refresh(client).status_code == 200

    db.expire_all()
    after = db.query(AuthSession).one().last_used_at
    assert after is not None
    assert before is None or after >= before


def test_rotation_chain_has_no_cycle(client, db):
    register(client)
    for _ in range(3):
        assert refresh(client).status_code == 200

    tokens = db.query(AuthRefreshToken).all()
    assert len(tokens) == 4
    by_id = {t.id: t for t in tokens}
    for token in tokens:
        seen = set()
        cursor = token
        while cursor.replaced_by_token_id is not None:
            assert cursor.id not in seen
            seen.add(cursor.id)
            cursor = by_id[cursor.replaced_by_token_id]
