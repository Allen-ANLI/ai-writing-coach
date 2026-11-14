"""Working Document GET/PUT integration tests on real PostgreSQL.

Covers API Spec §4.2: optimistic concurrency, server-derived text/word count,
revision increments, no snapshots on autosave, ownership isolation.
"""

import hashlib
from concurrent.futures import ThreadPoolExecutor

from essay_helpers import auth_headers, create_essay, save_document, tiptap_doc


def test_get_initial_working_document(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)

    response = client.get(f"/api/v1/essays/{essay['id']}/working-document", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["essay_id"] == essay["id"]
    assert data["server_revision"] == 1
    assert data["plain_text"] == ""
    assert data["word_count"] == 0
    assert data["content_json"] == {"type": "doc", "content": []}
    assert data["content_hash"] == hashlib.sha256(b"").hexdigest()


def test_put_saves_and_increments_revision(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)

    response = save_document(client, headers, essay["id"], base_revision=1, client_revision=7)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["server_revision"] == 2
    assert data["client_revision"] == 7
    assert data["saved"] is True
    assert data["saved_at"]

    fetched = client.get(f"/api/v1/essays/{essay['id']}/working-document", headers=headers).json()[
        "data"
    ]
    assert fetched["plain_text"] == "Hello world."
    assert fetched["word_count"] == 2
    assert fetched["server_revision"] == 2
    assert fetched["content_hash"] == hashlib.sha256(b"Hello world.").hexdigest()
    assert fetched["content_json"] == tiptap_doc("Hello world.")


def test_put_derives_text_when_client_values_omitted(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)

    response = save_document(
        client,
        headers,
        essay["id"],
        base_revision=1,
        paragraphs=("First paragraph.", "Second one."),
        include_client_values=False,
    )
    assert response.status_code == 200, response.text
    fetched = client.get(f"/api/v1/essays/{essay['id']}/working-document", headers=headers).json()[
        "data"
    ]
    assert fetched["plain_text"] == "First paragraph.\n\nSecond one."
    assert fetched["word_count"] == 4


def test_put_rejects_mismatched_plain_text(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)

    payload = {
        "base_revision": 1,
        "client_revision": 1,
        "content_json": tiptap_doc("Real text."),
        "plain_text": "Tampered text.",
    }
    response = client.put(
        f"/api/v1/essays/{essay['id']}/working-document", json=payload, headers=headers
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    fetched = client.get(f"/api/v1/essays/{essay['id']}/working-document", headers=headers).json()[
        "data"
    ]
    assert fetched["server_revision"] == 1
    assert fetched["plain_text"] == ""


def test_put_rejects_mismatched_word_count(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)

    payload = {
        "base_revision": 1,
        "client_revision": 1,
        "content_json": tiptap_doc("Hello world."),
        "word_count": 99,
    }
    response = client.put(
        f"/api/v1/essays/{essay['id']}/working-document", json=payload, headers=headers
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "word_count"


def test_put_stale_base_revision_conflicts_without_partial_write(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    assert save_document(client, headers, essay["id"], base_revision=1).status_code == 200

    stale = save_document(
        client, headers, essay["id"], base_revision=1, paragraphs=("Stale overwrite.",)
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "WORKING_DOCUMENT_CONFLICT"

    fetched = client.get(f"/api/v1/essays/{essay['id']}/working-document", headers=headers).json()[
        "data"
    ]
    assert fetched["server_revision"] == 2
    assert fetched["plain_text"] == "Hello world."


def test_put_invalid_document_rejected(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)

    payload = {
        "base_revision": 1,
        "client_revision": 1,
        "content_json": {"type": "paragraph"},
    }
    response = client.put(
        f"/api/v1/essays/{essay['id']}/working-document", json=payload, headers=headers
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_autosave_creates_no_snapshot(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    assert save_document(client, headers, essay["id"], base_revision=1).status_code == 200
    assert save_document(client, headers, essay["id"], base_revision=2).status_code == 200

    versions = client.get(f"/api/v1/essays/{essay['id']}/versions", headers=headers).json()["data"]
    assert len(versions["items"]) == 1
    assert versions["items"][0]["version_type"] == "original"


def test_autosave_bumps_essay_updated_at(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    assert save_document(client, headers, essay["id"], base_revision=1).status_code == 200

    detail = client.get(f"/api/v1/essays/{essay['id']}", headers=headers).json()["data"]
    assert detail["updated_at"] > essay["updated_at"]
    assert detail["working_document"]["server_revision"] == 2


def test_unicode_content_round_trips(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    text = "Emoji 🎉 and 中文 stay exact."

    response = save_document(client, headers, essay["id"], base_revision=1, paragraphs=(text,))
    assert response.status_code == 200, response.text
    fetched = client.get(f"/api/v1/essays/{essay['id']}/working-document", headers=headers).json()[
        "data"
    ]
    assert fetched["plain_text"] == text


def test_working_document_isolated_between_users(client):
    owner = auth_headers(client, "wd-owner@example.com")
    intruder = auth_headers(client, "wd-intruder@example.com")
    essay = create_essay(client, owner)

    assert (
        client.get(f"/api/v1/essays/{essay['id']}/working-document", headers=intruder).status_code
        == 404
    )
    assert save_document(client, intruder, essay["id"], base_revision=1).status_code == 404


def test_deleted_essay_working_document_not_found(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    assert client.delete(f"/api/v1/essays/{essay['id']}", headers=headers).status_code == 204

    assert (
        client.get(f"/api/v1/essays/{essay['id']}/working-document", headers=headers).status_code
        == 404
    )
    assert save_document(client, headers, essay["id"], base_revision=1).status_code == 404


def test_concurrent_saves_have_exactly_one_winner(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)

    def attempt(paragraph: str):
        return save_document(
            client, headers, essay["id"], base_revision=1, paragraphs=(paragraph,)
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(attempt, ["Writer A.", "Writer B."]))

    assert sorted(statuses) == [200, 409]
    fetched = client.get(f"/api/v1/essays/{essay['id']}/working-document", headers=headers).json()[
        "data"
    ]
    assert fetched["server_revision"] == 2
    assert fetched["plain_text"] in ("Writer A.", "Writer B.")
