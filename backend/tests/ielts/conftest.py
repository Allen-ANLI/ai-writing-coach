"""IELTS integration tests use the shared isolated PostgreSQL fixtures.

The shared truncate clears the seeded bank, so each test re-seeds it (the
seed is idempotent and fast).
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "essays"))

import pytest  # noqa: E402
from pg_fixtures import (  # noqa: F401,E402
    _clean_tables,
    client,
    db,
    session_factory,
    test_engine,
)

from app.modules.ielts.seed import seed_ielts  # noqa: E402


@pytest.fixture(autouse=True)
def _seed_bank(_clean_tables, session_factory):  # noqa: F811
    with session_factory() as session:
        seed_ielts(session)
        session.commit()
