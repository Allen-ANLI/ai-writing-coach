"""Auth integration test infrastructure.

Uses a dedicated real PostgreSQL database (<dev db>_test), migrated with
Alembic, truncated before every test. The app under test gets its DB sessions
from this test engine via dependency override; the dev database is untouched.
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

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[2]


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
        conn.execute(
            text("TRUNCATE auth_refresh_tokens, auth_sessions, user_profiles, users CASCADE")
        )
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
    # https base URL so Secure cookies are stored and sent by the test client.
    with TestClient(application, base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture
def db(session_factory):
    with session_factory() as session:
        yield session
