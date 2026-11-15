"""Knowledge base CRUD integration tests (API Spec §9)."""

from essay_helpers import auth_headers, create_essay


def _create(client, headers, **overrides):
    payload = {
        "english_text": "gain hands-on experience",
        "chinese_meaning": "获得实践经验",
        "usage_context": "Career and education",
        "topic": "Career",
        "register": "formal",
        "tags": ["career", "education"],
    }
    payload.update(overrides)
    return client.post("/api/v1/expressions", json=payload, headers=headers)


def test_create_expression_with_source(client):
    headers = auth_headers(client)
    response = _create(client, headers)
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["english_text"] == "gain hands-on experience"
    assert data["status"] == "collected"
    assert data["tags"] == ["career", "education"]


def test_duplicate_expression_rejected(client):
    headers = auth_headers(client)
    assert _create(client, headers).status_code == 201
    again = _create(client, headers, english_text="Gain Hands-On Experience")
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "RESOURCE_ALREADY_EXISTS"


def test_list_filters_and_pagination(client):
    headers = auth_headers(client)
    for i in range(3):
        assert (
            _create(
                client,
                headers,
                english_text=f"expression number {i}",
                topic="Career" if i < 2 else "Health",
            ).status_code
            == 201
        )

    listing = client.get("/api/v1/expressions?limit=2", headers=headers).json()["data"]
    assert len(listing["items"]) == 2
    assert listing["next_cursor"]
    page2 = client.get(
        f"/api/v1/expressions?limit=2&cursor={listing['next_cursor']}", headers=headers
    ).json()["data"]
    assert len(page2["items"]) == 1

    career = client.get("/api/v1/expressions?topic=Career", headers=headers).json()["data"]
    assert len(career["items"]) == 2

    search = client.post(
        "/api/v1/expressions/search", json={"query": "number 1"}, headers=headers
    ).json()["data"]
    assert len(search["items"]) == 1


def test_patch_archive_delete(client):
    headers = auth_headers(client)
    expression = _create(client, headers).json()["data"]

    patched = client.patch(
        f"/api/v1/expressions/{expression['id']}",
        json={"chinese_meaning": "更新后的含义", "status": "learning"},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["chinese_meaning"] == "更新后的含义"
    assert patched.json()["data"]["status"] == "learning"

    archived = client.post(f"/api/v1/expressions/{expression['id']}/archive", headers=headers)
    assert archived.status_code == 200
    assert archived.json()["data"]["status"] == "archived"

    deleted = client.delete(f"/api/v1/expressions/{expression['id']}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/expressions/{expression['id']}", headers=headers).status_code == 404


def test_expressions_isolated_between_users(client):
    owner = auth_headers(client, "expr-owner@example.com")
    intruder = auth_headers(client, "expr-intruder@example.com")
    expression = _create(client, owner).json()["data"]

    assert (
        client.get(f"/api/v1/expressions/{expression['id']}", headers=intruder).status_code == 404
    )
    assert (
        client.patch(
            f"/api/v1/expressions/{expression['id']}",
            json={"status": "archived"},
            headers=intruder,
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/expressions/{expression['id']}", headers=intruder).status_code
        == 404
    )
    listing = client.get("/api/v1/expressions", headers=intruder).json()["data"]
    assert listing["items"] == []


def test_create_with_essay_source_validates_ownership(client):
    owner = auth_headers(client, "src-owner@example.com")
    intruder = auth_headers(client, "src-intruder@example.com")
    essay = create_essay(client, owner)

    ok = _create(client, owner, essay_id=essay["id"], source_type="essay")
    assert ok.status_code == 201

    foreign = _create(client, intruder, english_text="another expression", essay_id=essay["id"])
    assert foreign.status_code == 404
