import os

# Automated tests ALWAYS use the deterministic mock provider, regardless of
# the developer's .env (real-provider separation requirement, 2026-11-15).
# Set before any app import so the cached settings pick it up.
os.environ["LLM_PROVIDER"] = "mock"
# The suite fires thousands of requests from one test client; the general
# per-IP limiter is exercised separately and disabled here.
os.environ["API_RATE_LIMIT_MAX_REQUESTS"] = "0"
# The temporary free-tier quota exemption (2026-11-16) is a deployment
# setting; the suite keeps enforcement ON to verify the mechanism itself.
# The exemption path is covered by a dedicated settings-monkeypatch test.
os.environ["FREE_PLAN_QUOTAS_DISABLED"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402

get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())
