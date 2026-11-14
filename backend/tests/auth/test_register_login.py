"""Registration and login: envelopes, hashing, credentials, normalization."""

from helpers import PASSWORD, auth_header, login, register

from app.core.security import hash_password, hash_refresh_token, verify_password
from app.modules.auth.models import AuthRefreshToken, AuthSession
from app.modules.users.models import User, UserProfile


def test_register_success_creates_user_profile_session_and_hashed_token(client, db):
    response = register(client)

    assert response.status_code == 201
    body = response.json()
    data = body["data"]
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 900
    assert data["user"]["email"] == "user@example.com"
    assert data["user"]["display_name"] == "Alex"
    assert isinstance(data["access_token"], str)
    assert body["meta"]["request_id"]

    user = db.query(User).one()
    assert user.email == "user@example.com"
    assert user.password_hash.startswith("$argon2id$")
    assert PASSWORD not in user.password_hash
    profile = db.query(UserProfile).one()
    assert profile.user_id == user.id
    assert profile.native_language == "zh"
    session = db.query(AuthSession).one()
    assert session.user_id == user.id
    assert session.revoked_at is None
    token = db.query(AuthRefreshToken).one()
    assert token.session_id == session.id
    cookie_value = response.cookies.get("awc_refresh_token")
    assert token.token_hash == hash_refresh_token(cookie_value)
    assert token.token_hash != cookie_value
    assert token.used_at is None


def test_register_duplicate_email_conflict(client):
    assert register(client).status_code == 201
    response = register(client)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "RESOURCE_ALREADY_EXISTS"


def test_register_normalizes_email(client):
    assert register(client, email="  User@Example.COM ").status_code == 201
    assert login(client, email="user@example.com").status_code == 200


def test_register_invalid_email_returns_validation_envelope(client):
    response = client.post(
        "/api/v1/auth/register", json={"email": "not-an-email", "password": PASSWORD}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "email"
    assert body["meta"]["request_id"]


def test_register_short_password_rejected(client):
    response = client.post(
        "/api/v1/auth/register", json={"email": "a@example.com", "password": "short"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_login_success_creates_new_session(client, db):
    register(client)
    response = login(client)

    assert response.status_code == 200
    assert response.json()["data"]["user"]["email"] == "user@example.com"
    assert response.cookies.get("awc_refresh_token")
    assert db.query(AuthSession).count() == 2


def test_login_wrong_password(client):
    register(client)
    response = login(client, password="WrongPassword123")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_unknown_email_same_error_as_wrong_password(client):
    register(client)
    unknown = login(client, email="nobody@example.com")
    wrong = login(client, password="WrongPassword123")

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["error"] == wrong.json()["error"]


def test_login_disabled_user_rejected(client, db):
    register(client)
    user = db.query(User).one()
    user.status = "disabled"
    db.commit()

    response = login(client)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_password_hashing_roundtrip():
    hashed = hash_password(PASSWORD)

    assert hashed.startswith("$argon2id$")
    assert verify_password(PASSWORD, hashed) is True
    assert verify_password("WrongPassword123", hashed) is False
    assert verify_password(PASSWORD, None) is False


def test_authenticated_request_carries_bearer(client):
    response = register(client)
    me = client.get("/api/v1/users/me", headers=auth_header(response))

    assert me.status_code == 200
    assert me.json()["data"]["email"] == "user@example.com"
