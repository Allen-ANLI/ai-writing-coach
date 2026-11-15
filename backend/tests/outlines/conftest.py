"""Outline integration tests use the shared isolated PostgreSQL fixtures."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "essays"))

from pg_fixtures import (  # noqa: F401,E402
    _clean_tables,
    client,
    db,
    session_factory,
    test_engine,
)
