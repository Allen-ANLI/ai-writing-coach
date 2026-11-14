"""Shared helpers for essay integration tests."""

PASSWORD = "SecurePassword123"


def auth_headers(client, email="essay-user@example.com") -> dict:
    response = client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def create_essay(client, headers, **overrides) -> dict:
    payload = {"writing_type": "free_writing", "title": "My essay"}
    payload.update(overrides)
    response = client.post("/api/v1/essays", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]
