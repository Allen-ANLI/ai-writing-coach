"""Data access for sessions and refresh tokens.

Locking convention: always lock the session row BEFORE token rows so refresh
and revocation paths cannot deadlock.
"""

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.auth.models import AuthRefreshToken, AuthSession


def create_session(
    db: Session,
    *,
    user_id: uuid.UUID,
    device_label: str | None,
    user_agent: str | None,
    ip_address: str | None,
    expires_at: datetime,
) -> AuthSession:
    session = AuthSession(
        user_id=user_id,
        device_label=device_label,
        user_agent=user_agent,
        ip_address=ip_address,
        expires_at=expires_at,
    )
    db.add(session)
    db.flush()
    return session


def create_refresh_token(
    db: Session,
    *,
    session_id: uuid.UUID,
    token_family_id: uuid.UUID,
    token_hash: str,
    expires_at: datetime,
) -> AuthRefreshToken:
    token = AuthRefreshToken(
        session_id=session_id,
        token_family_id=token_family_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(token)
    db.flush()
    return token


def get_token_by_hash(db: Session, token_hash: str) -> AuthRefreshToken | None:
    return db.execute(
        select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash)
    ).scalar_one_or_none()


def lock_session(db: Session, session_id: uuid.UUID) -> AuthSession | None:
    # populate_existing: the row may already be in the identity map from an
    # earlier unlocked read; the locked re-read must refresh its attributes.
    return db.execute(
        select(AuthSession)
        .where(AuthSession.id == session_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()


def lock_token(db: Session, token_id: uuid.UUID) -> AuthRefreshToken | None:
    return db.execute(
        select(AuthRefreshToken)
        .where(AuthRefreshToken.id == token_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()


def lock_user_sessions(db: Session, user_id: uuid.UUID) -> list[AuthSession]:
    return list(
        db.execute(
            select(AuthSession).where(AuthSession.user_id == user_id).with_for_update()
        ).scalars()
    )


def list_active_sessions(db: Session, user_id: uuid.UUID, now: datetime) -> list[AuthSession]:
    return list(
        db.execute(
            select(AuthSession)
            .where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
            )
            .order_by(AuthSession.created_at.desc())
        ).scalars()
    )


def get_session_for_user(
    db: Session, session_id: uuid.UUID, user_id: uuid.UUID
) -> AuthSession | None:
    return db.execute(
        select(AuthSession).where(AuthSession.id == session_id, AuthSession.user_id == user_id)
    ).scalar_one_or_none()


def revoke_session_tokens(db: Session, session_id: uuid.UUID, now: datetime) -> None:
    db.execute(
        update(AuthRefreshToken)
        .where(
            AuthRefreshToken.session_id == session_id,
            AuthRefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )


def revoke_token_family(db: Session, family_id: uuid.UUID, now: datetime) -> None:
    db.execute(
        update(AuthRefreshToken)
        .where(
            AuthRefreshToken.token_family_id == family_id,
            AuthRefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
