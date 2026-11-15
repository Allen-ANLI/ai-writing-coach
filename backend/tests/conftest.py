import os

# Automated tests ALWAYS use the deterministic mock provider, regardless of
# the developer's .env (real-provider separation requirement, 2026-11-15).
# Set before any app import so the cached settings pick it up.
os.environ["LLM_PROVIDER"] = "mock"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402

get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())
