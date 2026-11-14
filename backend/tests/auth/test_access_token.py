"""Access token validation: signature, expiry, issuer, audience, algorithm,
and server-side session state."""

import uuid
from datetime import timedelta

import jwt
from helpers import auth_header, register

from app.core.config import Settings, get_settings
from app.core.security import issue_access_token
from app.core.time import utcnow
from app.modules.auth.models import AuthSession


def _claims(response) -> dict:
    token = response.json()["data"]["access_token"]
    return jwt.decode(token, options={"verify_signature": False})


def test_missing_token_rejected(client):
    response = client.get("/api/v1/users/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_malformed_token_rejected(client):
    response = client.get("/api/v1/users/me", headers={"Authorization": "Bearer not.a.jwt"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_expired_token_rejected(client, monkeypatch):
    response = register(client)
    claims = _claims(response)
    monkeypatch.setattr(
        "app.core.security.get_settings",
        lambda: Settings(_env_file=None, access_token_ttl_seconds=-10),
    )
    expired, _ = issue_access_token(uuid.UUID(claims["sub"]), uuid.UUID(claims["sid"]))

    result = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {expired}"})

    assert result.status_code == 401
    assert result.json()["error"]["code"] == "TOKEN_EXPIRED"


def test_tampered_signature_rejected(client):
    response = register(client)
    token = response.json()["data"]["access_token"]
    tampered = token[:-6] + ("aaaaaa" if not token.endswith("aaaaaa") else "bbbbbb")

    result = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {tampered}"})

    assert result.status_code == 401
    assert result.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def _craft(client, response, **overrides) -> str:
    settings = get_settings()
    claims = _claims(response)
    claims.update(overrides)
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def test_wrong_issuer_rejected(client):
    response = register(client)
    token = _craft(client, response, iss="evil-issuer")

    result = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})

    assert result.status_code == 401


def test_wrong_audience_rejected(client):
    response = register(client)
    token = _craft(client, response, aud="some-other-api")

    result = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})

    assert result.status_code == 401


def test_algorithm_not_accepted_from_token(client):
    response = register(client)
    settings = get_settings()
    claims = _claims(response)
    token = jwt.encode(claims, settings.jwt_secret, algorithm="HS512")

    result = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})

    assert result.status_code == 401
    assert result.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_revoked_session_rejects_access_token(client, db):
    response = register(client)
    claims = _claims(response)
    session = db.get(AuthSession, uuid.UUID(claims["sid"]))
    session.revoked_at = utcnow()
    db.commit()

    result = client.get("/api/v1/users/me", headers=auth_header(response))

    assert result.status_code == 401
    assert result.json()["error"]["code"] == "REFRESH_TOKEN_REVOKED"


def test_expired_session_rejects_access_token(client, db):
    response = register(client)
    claims = _claims(response)
    session = db.get(AuthSession, uuid.UUID(claims["sid"]))
    session.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()

    result = client.get("/api/v1/users/me", headers=auth_header(response))

    assert result.status_code == 401


def test_sub_session_mismatch_rejected(client):
    response_a = register(client, email="a@example.com")
    response_b = register(client, email="b@example.com")
    claims_a = _claims(response_a)
    claims_b = _claims(response_b)
    # Valid signature, but user A paired with user B's session.
    token = _craft(client, response_a, sid=claims_b["sid"])
    assert claims_a["sub"] != claims_b["sub"]

    result = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})

    assert result.status_code == 401
