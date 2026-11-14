"""GET/PATCH /users/me: shape, allowed fields, validation, isolation."""

from helpers import auth_header, register


def test_get_me_returns_user_and_profile(client):
    response = register(client)

    me = client.get("/api/v1/users/me", headers=auth_header(response))

    assert me.status_code == 200
    data = me.json()["data"]
    assert data["email"] == "user@example.com"
    assert data["status"] == "active"
    profile = data["profile"]
    assert profile["display_name"] == "Alex"
    assert profile["native_language"] == "zh"
    assert profile["preferences"] == {}
    assert "password_hash" not in data
    assert "password" not in me.text


def test_patch_me_updates_allowed_fields(client):
    response = register(client)

    patched = client.patch(
        "/api/v1/users/me",
        headers=auth_header(response),
        json={
            "display_name": "New Name",
            "english_level": "intermediate",
            "target_exam": "ielts",
            "target_writing_score": 7.5,
            "preferred_english_variant": "british",
        },
    )

    assert patched.status_code == 200
    profile = patched.json()["data"]["profile"]
    assert profile["display_name"] == "New Name"
    assert profile["english_level"] == "intermediate"
    assert profile["target_exam"] == "ielts"
    assert float(profile["target_writing_score"]) == 7.5
    assert profile["preferred_english_variant"] == "british"

    again = client.get("/api/v1/users/me", headers=auth_header(response))
    assert again.json()["data"]["profile"]["display_name"] == "New Name"


def test_patch_me_rejects_unknown_field(client):
    response = register(client)

    patched = client.patch(
        "/api/v1/users/me",
        headers=auth_header(response),
        json={"status": "disabled", "email": "hijack@example.com"},
    )

    assert patched.status_code == 422
    assert patched.json()["error"]["code"] == "VALIDATION_ERROR"


def test_patch_me_rejects_out_of_range_score(client):
    response = register(client)

    patched = client.patch(
        "/api/v1/users/me", headers=auth_header(response), json={"target_writing_score": 10.0}
    )

    assert patched.status_code == 422


def test_profile_isolation_between_users(client):
    alice = register(client, email="alice@example.com", display_name="Alice")
    bob = register(client, email="bob@example.com", display_name="Bob")

    client.patch(
        "/api/v1/users/me", headers=auth_header(alice), json={"display_name": "Alice Updated"}
    )

    bob_me = client.get("/api/v1/users/me", headers=auth_header(bob))
    assert bob_me.json()["data"]["email"] == "bob@example.com"
    assert bob_me.json()["data"]["profile"]["display_name"] == "Bob"
    alice_me = client.get("/api/v1/users/me", headers=auth_header(alice))
    assert alice_me.json()["data"]["profile"]["display_name"] == "Alice Updated"


def test_users_me_requires_authentication(client):
    assert client.get("/api/v1/users/me").status_code == 401
    assert client.patch("/api/v1/users/me", json={"display_name": "X"}).status_code == 401
