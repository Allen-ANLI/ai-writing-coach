"""Database-level constraints: unique email, unique token hash, and the
partial unique index enforcing one active token per session."""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.time import utcnow
from app.modules.auth.models import AuthRefreshToken, AuthSession
from app.modules.users.models import User


def _user(db, email="constraint@example.com") -> User:
    user = User(email=email, password_hash="x", status="active")
    db.add(user)
    db.flush()
    return user


def _session(db, user: User) -> AuthSession:
    session = AuthSession(user_id=user.id, expires_at=utcnow() + timedelta(days=1))
    db.add(session)
    db.flush()
    return session


def _token(db, session: AuthSession, token_hash: str) -> AuthRefreshToken:
    token = AuthRefreshToken(
        session_id=session.id,
        token_family_id=uuid.uuid4(),
        token_hash=token_hash,
        expires_at=utcnow() + timedelta(days=1),
    )
    db.add(token)
    db.flush()
    return token


def test_unique_email_constraint(db):
    _user(db, email="dup@example.com")
    with pytest.raises(IntegrityError):
        _user(db, email="dup@example.com")
    db.rollback()


def test_unique_token_hash_constraint(db):
    user = _user(db)
    session = _session(db, user)
    _token(db, session, "same-hash")
    with pytest.raises(IntegrityError):
        _token(db, session, "same-hash")
    db.rollback()


def test_one_active_token_per_session_constraint(db):
    user = _user(db)
    session = _session(db, user)
    _token(db, session, "hash-1")
    with pytest.raises(IntegrityError):
        _token(db, session, "hash-2")
    db.rollback()


def test_consumed_token_frees_the_active_slot(db):
    user = _user(db)
    session = _session(db, user)
    first = _token(db, session, "hash-1")
    first.used_at = utcnow()
    db.flush()
    _token(db, session, "hash-2")
    db.rollback()
