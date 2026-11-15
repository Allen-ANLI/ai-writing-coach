"""Shared isolated-PostgreSQL fixtures for integration tests.

A dedicated test database (<dev db>_test) is created and migrated once per
session; every test starts from truncated tables. The dev database is never
touched. Import these fixtures into a package conftest to use them.
"""

import os
import pathlib
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.rate_limit import reset_rate_limiter
from app.infrastructure.database import get_db
from app.main import create_app

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]

_TRUNCATE = (
    # subscription_plans is migration-seeded reference data (never mutated by
    # tests), so it survives truncation; per-user billing rows are cleared.
    "TRUNCATE payment_transactions, usage_meters, user_subscriptions, "
    "learning_tasks, learning_plans, workflow_events, workflows, outline_nodes, "
    "writing_outlines, "
    "essay_rewrites, essay_evaluations, user_favorite_questions, ielts_question_tags, "
    "ielts_questions, question_tags, "
    "expression_reviews, expression_progress, user_weaknesses, expression_embeddings, "
    "expression_suggestion_items, expression_suggestions, expression_sources, user_expressions, "
    "issue_teachings, issue_suggestions, writing_issues, ai_usage_logs, writing_sessions, "
    "essay_edit_events, idempotency_keys, essay_versions, essay_working_documents, essays, "
    "password_reset_tokens, auth_refresh_tokens, auth_sessions, user_profiles, users CASCADE"
)


def _test_db_url():
    url = make_url(get_settings().database_url)
    return url.set(database=url.database + "_test")


@pytest.fixture(scope="session")
def test_engine():
    url = _test_db_url()
    admin_engine = create_engine(
        get_settings().database_url,
        isolation_level="AUTOCOMMIT",
        connect_args={"connect_timeout": 5},
    )
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin_engine.dispose()

    env = os.environ.copy()
    env["DATABASE_URL"] = url.render_as_string(hide_password=False)
    migrated = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert migrated.returncode == 0, migrated.stderr

    engine = create_engine(url, connect_args={"connect_timeout": 5})
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables(test_engine):
    with test_engine.begin() as conn:
        conn.execute(text(_TRUNCATE))
    reset_rate_limiter()


@pytest.fixture
def session_factory(test_engine):
    return sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def client(session_factory):
    application = create_app()

    def override_get_db():
        with session_factory() as session:
            yield session

    application.dependency_overrides[get_db] = override_get_db
    # Background tasks (evaluations/rewrites) must use the isolated test DB.
    application.state.session_factory = session_factory
    # https base URL so Secure cookies are stored and sent by the test client.
    with TestClient(application, base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture
def db(session_factory):
    with session_factory() as session:
        yield session
