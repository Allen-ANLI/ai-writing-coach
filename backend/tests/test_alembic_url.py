"""Alembic must accept database URLs with percent-encoded credentials.

Runs offline SQL generation (no connection) in a subprocess so the real
alembic/env.py is exercised end to end. Before the fix, ConfigParser
interpolation raised on URLs containing '%'.
"""

import os
import pathlib
import subprocess
import sys

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]


def test_offline_sql_generation_with_percent_encoded_url():
    env = os.environ.copy()
    env["DATABASE_URL"] = "postgresql+psycopg://awc:p%40ss%25word@localhost:5432/ai_writing_coach"

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    assert "CREATE EXTENSION IF NOT EXISTS vector" in result.stdout
