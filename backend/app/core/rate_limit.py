"""In-process sliding-window rate limiter (reservation for register/login).

Deliberately simple and dependency-free: correct for a single worker, and the
storage point is isolated so a shared store can replace it later without
touching routers. Never logs keys or request contents.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.config import get_settings
from app.core.exceptions import ApiError

_windows: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def reset_rate_limiter() -> None:
    with _lock:
        _windows.clear()


def enforce_auth_rate_limit(request: Request, scope: str) -> None:
    settings = get_settings()
    key = f"{scope}:{request.client.host if request.client else 'unknown'}"
    now = time.monotonic()
    window = settings.auth_rate_limit_window_seconds
    limit = settings.auth_rate_limit_max_requests
    with _lock:
        entries = _windows[key]
        while entries and now - entries[0] > window:
            entries.popleft()
        if len(entries) >= limit:
            raise ApiError(429, "RATE_LIMIT_EXCEEDED", "Too many requests. Try again later.")
        entries.append(now)


def check_general_rate_limit(client_host: str) -> bool:
    """Sliding-window per-IP limit for the whole API. True if allowed.

    In-process (single worker) by design; the storage point is isolated so a
    shared store (e.g. Redis) can replace it for multi-worker deployments.
    """
    settings = get_settings()
    limit = settings.api_rate_limit_max_requests
    if limit <= 0:
        return True
    key = f"api:{client_host}"
    now = time.monotonic()
    window = settings.api_rate_limit_window_seconds
    with _lock:
        entries = _windows[key]
        while entries and now - entries[0] > window:
            entries.popleft()
        if len(entries) >= limit:
            return False
        entries.append(now)
    return True
