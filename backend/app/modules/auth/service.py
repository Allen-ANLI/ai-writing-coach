"""Authentication business logic.

Invariants (AGENTS.md §4, ERD §5, API Spec §3.1):
- A session is a stable device login; rotation never creates a new session.
- Only refresh token hashes are stored; plaintext exists in the cookie only.
- Consuming the old token and creating its replacement is one transaction.
- Reuse of a consumed token revokes the whole token family and the session.
- Lock order is always session row first, then token rows (deadlock-free).
"""

import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ApiError
from app.core.security import (
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    issue_access_token,
    verify_password,
)
from app.core.time import utcnow
from app.modules.auth import repository
from app.modules.auth.models import AuthSession
from app.modules.users import repository as users_repository
from app.modules.users.models import User


@dataclass(frozen=True)
class DeviceInfo:
    device_label: str | None
    user_agent: str | None
    ip_address: str | None


@dataclass(frozen=True)
class AuthResult:
    user: User
    access_token: str
    expires_in: int
    refresh_token: str


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _start_session(db: Session, user: User, device: DeviceInfo) -> tuple[AuthSession, str]:
    settings = get_settings()
    now = utcnow()
    session = repository.create_session(
        db,
        user_id=user.id,
        device_label=device.device_label,
        user_agent=device.user_agent,
        ip_address=device.ip_address,
        expires_at=now + timedelta(days=settings.refresh_token_ttl_days),
    )
    plaintext = generate_refresh_token()
    repository.create_refresh_token(
        db,
        session_id=session.id,
        token_family_id=uuid.uuid4(),
        token_hash=hash_refresh_token(plaintext),
        expires_at=session.expires_at,
    )
    return session, plaintext


def _auth_result(user: User, session: AuthSession, refresh_token: str) -> AuthResult:
    access_token, ttl = issue_access_token(user.id, session.id)
    return AuthResult(
        user=user, access_token=access_token, expires_in=ttl, refresh_token=refresh_token
    )


def register(
    db: Session, *, email: str, password: str, display_name: str | None, device: DeviceInfo
) -> AuthResult:
    normalized = _normalize_email(email)
    if users_repository.get_by_email(db, normalized) is not None:
        raise ApiError(409, "RESOURCE_ALREADY_EXISTS", "Email is already registered.")
    # Hash outside the write transaction to keep it short.
    password_hash = hash_password(password)
    user = users_repository.create_with_profile(
        db, email=normalized, password_hash=password_hash, display_name=display_name
    )
    session, plaintext = _start_session(db, user, device)
    db.commit()
    return _auth_result(user, session, plaintext)


def login(db: Session, *, email: str, password: str, device: DeviceInfo) -> AuthResult:
    user = users_repository.get_by_email(db, _normalize_email(email))
    # verify_password handles a missing user with a decoy hash (timing parity).
    if not verify_password(password, user.password_hash if user else None):
        raise ApiError(401, "INVALID_CREDENTIALS", "Invalid email or password.")
    if user.status != "active":
        raise ApiError(401, "AUTHENTICATION_REQUIRED", "Account is not active.")
    session, plaintext = _start_session(db, user, device)
    db.commit()
    return _auth_result(user, session, plaintext)


def refresh(db: Session, *, refresh_token: str) -> AuthResult:
    settings = get_settings()
    now = utcnow()
    candidate = repository.get_token_by_hash(db, hash_refresh_token(refresh_token))
    if candidate is None:
        raise ApiError(401, "AUTHENTICATION_REQUIRED", "Refresh token is invalid.")

    # Lock session first, then the token row (consistent lock order).
    session = repository.lock_session(db, candidate.session_id)
    token = repository.lock_token(db, candidate.id)
    if session is None or token is None:
        raise ApiError(401, "AUTHENTICATION_REQUIRED", "Refresh token is invalid.")

    if token.used_at is not None:
        # Reuse of a consumed token: revoke the family and the session.
        repository.revoke_token_family(db, token.token_family_id, now)
        session.revoked_at = now
        db.commit()
        raise ApiError(401, "REFRESH_TOKEN_REUSE_DETECTED", "Refresh token reuse detected.")

    if token.revoked_at is not None or session.revoked_at is not None:
        raise ApiError(401, "REFRESH_TOKEN_REVOKED", "Refresh token has been revoked.")
    if token.expires_at <= now or session.expires_at <= now:
        raise ApiError(401, "AUTHENTICATION_REQUIRED", "Refresh token has expired.")

    user = users_repository.get_by_id(db, session.user_id)
    if user is None or user.status != "active":
        raise ApiError(401, "AUTHENTICATION_REQUIRED", "Account is not active.")

    plaintext = generate_refresh_token()
    # Consume the old token BEFORE inserting the replacement: the partial
    # unique index allows only one active token per session, so the UPDATE
    # must reach the database first (same transaction, ordered flushes).
    token.used_at = now
    db.flush()
    replacement = repository.create_refresh_token(
        db,
        session_id=session.id,
        token_family_id=token.token_family_id,
        token_hash=hash_refresh_token(plaintext),
        expires_at=now + timedelta(days=settings.refresh_token_ttl_days),
    )
    token.replaced_by_token_id = replacement.id
    session.last_used_at = now
    db.commit()
    return _auth_result(user, session, plaintext)


def logout(db: Session, *, session_id: uuid.UUID) -> None:
    now = utcnow()
    session = repository.lock_session(db, session_id)
    if session is not None and session.revoked_at is None:
        session.revoked_at = now
        repository.revoke_session_tokens(db, session.id, now)
    db.commit()


def logout_all(db: Session, *, user_id: uuid.UUID) -> int:
    now = utcnow()
    count = 0
    for session in repository.lock_user_sessions(db, user_id):
        if session.revoked_at is None:
            session.revoked_at = now
            repository.revoke_session_tokens(db, session.id, now)
            count += 1
    db.commit()
    return count


def list_sessions(db: Session, *, user_id: uuid.UUID) -> list[AuthSession]:
    return repository.list_active_sessions(db, user_id, utcnow())


def revoke_session(db: Session, *, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
    session = repository.get_session_for_user(db, session_id, user_id)
    if session is None or session.revoked_at is not None:
        # 404 for foreign or already-revoked sessions avoids enumeration.
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Session not found.")
    now = utcnow()
    locked = repository.lock_session(db, session.id)
    if locked is None or locked.revoked_at is not None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Session not found.")
    locked.revoked_at = now
    repository.revoke_session_tokens(db, locked.id, now)
    db.commit()
