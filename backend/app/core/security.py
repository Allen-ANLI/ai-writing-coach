"""Security primitives: Argon2id password hashing, JWT access tokens, and
opaque refresh token generation/hashing. No business logic lives here."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

_hasher = PasswordHasher()

# Constant-time decoy hash so login timing does not reveal whether an email
# exists. Generated once at import; never matches any real password.
_DECOY_HASH = _hasher.hash("decoy-password-for-timing-equalization")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        if password_hash is None:
            # Decoy verification keeps timing parity for unknown emails.
            _hasher.verify(_DECOY_HASH, password)
            return False
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_access_token(user_id: uuid.UUID, session_id: uuid.UUID) -> tuple[str, int]:
    settings = get_settings()
    now = datetime.now(UTC)
    ttl = settings.access_token_ttl_seconds
    claims = {
        "sub": str(user_id),
        "sid": str(session_id),
        "jti": str(uuid.uuid4()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
    }
    token = jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, ttl


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify signature, expiry, issuer, audience with a fixed algorithm.

    Raises jwt.ExpiredSignatureError / jwt.InvalidTokenError subclasses.
    """
    settings = get_settings()
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        options={"require": ["exp", "iat", "sub", "sid", "iss", "aud", "jti"]},
    )
