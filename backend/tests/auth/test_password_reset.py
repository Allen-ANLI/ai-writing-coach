"""Password reset tests (Slice 11, R7): token lifecycle, no enumeration,
session revocation. The console email provider logs the link; tests read the
token hash relationship from the DB instead of parsing logs.
"""

import secrets

from essay_helpers import PASSWORD, auth_headers
from sqlalchemy import select

from app.core.security import hash_refresh_token
from app.modules.auth.models import AuthSession, PasswordResetToken


def _latest_token(db):
    return (
        db.execute(select(PasswordResetToken).order_by(PasswordResetToken.created_at.desc()))
        .scalars()
        .first()
    )


def _request(client, email):
    return client.post("/api/v1/auth/password-reset/request", json={"email": email})


def test_reset_request_and_confirm_flow(client, db):
    email = "reset-flow@example.com"
    auth_headers(client, email=email)

    response = _request(client, email)
    assert response.status_code == 202
    assert response.json()["data"]["accepted"] is True

    # The raw token is only in the (console) email; reconstruct via the DB by
    # confirming with a token we generate is impossible — instead verify the
    # stored hash exists and use the service-level token through the email log.
    record = _latest_token(db)
    assert record is not None
    assert record.used_at is None

    # Confirm with a wrong token fails.
    bad = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": secrets.token_urlsafe(32), "new_password": "NewPassword456"},
    )
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "INVALID_RESET_TOKEN"


def test_reset_confirm_with_real_token(client, db, caplog):
    import logging

    email = "reset-real@example.com"
    auth_headers(client, email=email)
    with caplog.at_level(logging.INFO, logger="app.infrastructure.email"):
        _request(client, email)
    link_line = next(r.message for r in caplog.records if "reset-password?token=" in r.message)
    token = link_line.split("reset-password?token=")[1].split("\n")[0].strip()

    response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "NewPassword456"},
    )
    assert response.status_code == 200, response.text

    record = _latest_token(db)
    assert record.used_at is not None
    assert record.token_hash == hash_refresh_token(token)

    # Old password no longer works; new one does.
    old_login = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert old_login.status_code == 401
    new_login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "NewPassword456"}
    )
    assert new_login.status_code == 200

    # Token is single-use.
    reuse = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "AnotherPassword789"},
    )
    assert reuse.status_code == 400


def test_reset_revokes_existing_sessions(client, db, caplog):
    import logging

    email = "reset-sessions@example.com"
    auth_headers(client, email=email)
    sessions_before = list(
        db.execute(select(AuthSession).where(AuthSession.revoked_at.is_(None))).scalars()
    )
    assert sessions_before

    with caplog.at_level(logging.INFO, logger="app.infrastructure.email"):
        _request(client, email)
    link_line = next(r.message for r in caplog.records if "reset-password?token=" in r.message)
    token = link_line.split("reset-password?token=")[1].split("\n")[0].strip()

    response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "NewPassword456"},
    )
    assert response.status_code == 200
    sessions_after = list(
        db.execute(select(AuthSession).where(AuthSession.revoked_at.is_(None))).scalars()
    )
    assert sessions_after == []


def test_reset_request_unknown_email_is_silent(client, db):
    response = _request(client, "nobody@example.com")
    assert response.status_code == 202
    assert db.execute(select(PasswordResetToken)).scalars().first() is None


def test_reset_confirm_short_password_rejected(client):
    response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": secrets.token_urlsafe(32), "new_password": "short"},
    )
    assert response.status_code == 422


def test_expired_token_rejected(client, db, caplog):
    import logging
    from datetime import timedelta

    from app.core.time import utcnow

    email = "reset-expired@example.com"
    auth_headers(client, email=email)
    with caplog.at_level(logging.INFO, logger="app.infrastructure.email"):
        _request(client, email)
    link_line = next(r.message for r in caplog.records if "reset-password?token=" in r.message)
    token = link_line.split("reset-password?token=")[1].split("\n")[0].strip()

    record = _latest_token(db)
    record.expires_at = utcnow() - timedelta(minutes=1)
    db.commit()

    response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "NewPassword456"},
    )
    assert response.status_code == 400
