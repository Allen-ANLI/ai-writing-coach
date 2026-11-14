"""Authentication dependencies: the user identity always comes from the
verified access token + server-side session state, never from client input."""

import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ApiError
from app.core.security import decode_access_token
from app.core.time import utcnow
from app.infrastructure.database import get_db
from app.modules.auth.models import AuthSession
from app.modules.users.models import User

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthContext:
    user: User
    session: AuthSession


def get_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> AuthContext:
    if credentials is None:
        raise ApiError(401, "AUTHENTICATION_REQUIRED", "Authentication required.")
    try:
        claims = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise ApiError(401, "TOKEN_EXPIRED", "Access token has expired.") from None
    except jwt.InvalidTokenError:
        raise ApiError(401, "AUTHENTICATION_REQUIRED", "Access token is invalid.") from None

    session = db.get(AuthSession, uuid.UUID(claims["sid"]))
    now = utcnow()
    if session is None or session.revoked_at is not None or session.expires_at <= now:
        raise ApiError(401, "REFRESH_TOKEN_REVOKED", "Session is no longer valid.")
    user = db.get(User, uuid.UUID(claims["sub"]))
    if user is None or user.status != "active" or session.user_id != user.id:
        raise ApiError(401, "AUTHENTICATION_REQUIRED", "Authentication required.")
    return AuthContext(user=user, session=session)


def get_current_user(context: AuthContext = Depends(get_auth_context)) -> User:
    return context.user


def verify_refresh_origin(request: Request) -> None:
    """CSRF defense for the cookie-authenticated refresh endpoint.

    The refresh cookie is SameSite=Strict; additionally, when a browser
    Origin header is present it must match the configured local origins.
    No extra request header is required, keeping the OpenAPI contract shape.
    """
    origin = request.headers.get("origin")
    if origin is not None and origin not in get_settings().cors_origins:
        raise ApiError(403, "RESOURCE_ACCESS_DENIED", "Cross-origin refresh is not allowed.")
