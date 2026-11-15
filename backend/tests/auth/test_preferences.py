"""Preferences tests (Slice 9): defaults, merge patch, validation."""

from essay_helpers import auth_headers


def test_preferences_defaults(client):
    headers = auth_headers(client)
    response = client.get("/api/v1/users/me/preferences", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data == {
        "auto_grammar_check": True,
        "auto_expression_assist": True,
        "daily_review_goal": None,
        "ui_language": "zh",
        "ghost_hints_enabled": True,
    }


def test_ghost_hints_toggle_persists(client):
    headers = auth_headers(client)
    response = client.patch(
        "/api/v1/users/me/preferences",
        json={"ghost_hints_enabled": False},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["ghost_hints_enabled"] is False
    again = client.get("/api/v1/users/me/preferences", headers=headers).json()["data"]
    assert again["ghost_hints_enabled"] is False


def test_preferences_patch_merges_and_persists(client):
    headers = auth_headers(client)
    response = client.patch(
        "/api/v1/users/me/preferences",
        json={"daily_review_goal": 20, "ui_language": "en"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["daily_review_goal"] == 20

    response = client.patch(
        "/api/v1/users/me/preferences",
        json={"auto_grammar_check": False},
        headers=headers,
    )
    data = response.json()["data"]
    assert data["auto_grammar_check"] is False
    assert data["daily_review_goal"] == 20  # untouched key preserved
    assert data["ui_language"] == "en"

    again = client.get("/api/v1/users/me/preferences", headers=headers).json()["data"]
    assert again == data


def test_preferences_validation(client):
    headers = auth_headers(client)
    response = client.patch(
        "/api/v1/users/me/preferences", json={"daily_review_goal": 0}, headers=headers
    )
    assert response.status_code == 422
    response = client.patch(
        "/api/v1/users/me/preferences", json={"ui_language": "fr"}, headers=headers
    )
    assert response.status_code == 422
    response = client.patch(
        "/api/v1/users/me/preferences", json={"unknown_key": 1}, headers=headers
    )
    assert response.status_code == 422


def test_preferences_require_auth(client):
    assert client.get("/api/v1/users/me/preferences").status_code == 401
    assert client.patch("/api/v1/users/me/preferences", json={}).status_code == 401
