"""Rolling back the pgvector baseline must not drop the extension.

Requires the real PostgreSQL container; skipped when unreachable. The test
restores 'head' afterwards so the database is left as it was found.
"""

import pathlib
import subprocess
import sys

import pytest
from sqlalchemy import text

from app.infrastructure.database import engine

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]


def _database_reachable() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _database_reachable(),
    reason="PostgreSQL is not reachable; start it with 'docker compose up -d db'",
)


def _alembic(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_downgrade_keeps_extension_and_upgrade_restores_head():
    downgraded = _alembic("downgrade", "-1")
    assert downgraded.returncode == 0, downgraded.stderr
    try:
        with engine.connect() as connection:
            version = connection.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            ).scalar_one_or_none()
        assert version is not None
    finally:
        restored = _alembic("upgrade", "head")
        assert restored.returncode == 0, restored.stderr
