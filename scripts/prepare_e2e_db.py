"""Prepare the isolated E2E database for Playwright runs.

Creates <dev db>_test if missing and applies all Alembic migrations. Used by
frontend/e2e/global-setup.ts so E2E tests never touch development data.
"""

import os
import pathlib
import subprocess
import sys

import psycopg
from sqlalchemy.engine import make_url

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402


def main() -> int:
    base_url = make_url(get_settings().database_url)
    test_url = base_url.set(database=base_url.database + "_test")
    # psycopg needs a plain DSN without SQLAlchemy's '+psycopg' driver suffix.
    admin_dsn = base_url.set(drivername="postgresql").render_as_string(hide_password=False)

    with psycopg.connect(admin_dsn, autocommit=True, connect_timeout=5) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (test_url.database,)
        ).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{test_url.database}"')
            print(f"created database {test_url.database}")

    env = os.environ.copy()
    env["DATABASE_URL"] = test_url.render_as_string(hide_password=False)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        print(result.stderr)
        return result.returncode
    print(f"e2e database ready: {test_url.database}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
