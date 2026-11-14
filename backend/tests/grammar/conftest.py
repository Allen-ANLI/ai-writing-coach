"""Grammar integration tests use the shared isolated PostgreSQL fixtures."""

import pathlib
import sys

# essay_helpers lives in the essays test package; make it importable even when
# only the grammar suite is selected.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "essays"))

from pg_fixtures import (  # noqa: F401,E402
    _clean_tables,
    client,
    db,
    session_factory,
    test_engine,
)
