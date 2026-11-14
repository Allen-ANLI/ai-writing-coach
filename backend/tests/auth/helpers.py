"""Shared helpers for auth integration tests."""

from app.core.config import get_settings

PASSWORD = "SecurePassword123"


def register(client, email="user@example.com", password=PASSWORD, display_name="Alex"):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": display_name},
    )


def login(client, email="user@example.com", password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def auth_header(response) -> dict:
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def refresh_cookie_value(response) -> str:
    return response.cookies.get(get_settings().refresh_cookie_name)


def refresh(client, cookie_value: str | None = None, origin: str | None = None):
    kwargs = {}
    if cookie_value is not None:
        kwargs["cookies"] = {get_settings().refresh_cookie_name: cookie_value}
    if origin is not None:
        kwargs["headers"] = {"Origin": origin}
    return client.post("/api/v1/auth/refresh", **kwargs)
