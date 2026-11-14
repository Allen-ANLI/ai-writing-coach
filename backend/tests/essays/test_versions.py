"""Snapshot / version / restore integration tests on real PostgreSQL.

Covers API Spec §4.3–4.4 and AGENTS §4 invariants: immutable snapshots,
exact-revision snapshots, restore copies without mutating the source,
atomic Edit Events, idempotent snapshot creation, ownership isolation.
"""

import uuid

from essay_helpers import auth_headers, create_essay, save_document
from sqlalchemy import select

from app.modules.essays.models import EssayEditEvent


def _snapshot(client, headers, essay_id, source_revision, version_type="checkpoint", label=None):
    payload = {"source_revision": source_revision, "version_type": version_type}
    if label is not None:
        payload["label"] = label
    return client.post(f"/api/v1/essays/{essay_id}/snapshots", json=payload, headers=headers)


def test_create_checkpoint_snapshot(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    assert (
        save_document(
            client, headers, essay["id"], base_revision=1, paragraphs=("Snapshot me.",)
        ).status_code
        == 200
    )

    response = _snapshot(client, headers, essay["id"], 2, label="Before AI revision")
    assert response.status_code == 201, response.text
    version = response.json()["data"]
    assert version["version_no"] == 2
    assert version["version_type"] == "checkpoint"
    assert version["label"] == "Before AI revision"
    assert version["source_revision"] == 2
    assert version["plain_text"] == "Snapshot me."
    assert version["word_count"] == 2
    assert version["parent_version_id"] == essay["original_version_id"]
    assert version["created_by"]


def test_snapshot_requires_current_revision(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    assert save_document(client, headers, essay["id"], base_revision=1).status_code == 200

    response = _snapshot(client, headers, essay["id"], 1)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DOCUMENT_VERSION_CONFLICT"


def test_snapshot_rejects_original_and_ai_rewrite_types(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)

    for version_type in ("original", "ai_rewrite", "working"):
        response = _snapshot(client, headers, essay["id"], 1, version_type=version_type)
        assert response.status_code == 422, version_type


def test_version_numbers_increment(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    assert save_document(client, headers, essay["id"], base_revision=1).status_code == 200

    first = _snapshot(client, headers, essay["id"], 2).json()["data"]
    assert (
        save_document(
            client, headers, essay["id"], base_revision=2, paragraphs=("More text.",)
        ).status_code
        == 200
    )
    second = _snapshot(client, headers, essay["id"], 3).json()["data"]

    assert first["version_no"] == 2
    assert second["version_no"] == 3
    assert second["parent_version_id"] == first["id"]


def test_versions_list_pagination(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    for revision in (1, 2, 3):
        assert (
            save_document(
                client,
                headers,
                essay["id"],
                base_revision=revision,
                paragraphs=(f"Version {revision}.",),
            ).status_code
            == 200
        )
        assert _snapshot(client, headers, essay["id"], revision + 1).status_code == 201

    page1 = client.get(f"/api/v1/essays/{essay['id']}/versions?limit=2", headers=headers).json()[
        "data"
    ]
    assert len(page1["items"]) == 2
    assert page1["next_cursor"]
    assert [item["version_no"] for item in page1["items"]] == [4, 3]

    page2 = client.get(
        f"/api/v1/essays/{essay['id']}/versions?limit=2&cursor={page1['next_cursor']}",
        headers=headers,
    ).json()["data"]
    assert [item["version_no"] for item in page2["items"]] == [2, 1]
    assert page2["next_cursor"] is None


def test_version_detail_contains_content(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    assert (
        save_document(
            client, headers, essay["id"], base_revision=1, paragraphs=("Detail content.",)
        ).status_code
        == 200
    )
    version = _snapshot(client, headers, essay["id"], 2).json()["data"]

    detail = client.get(
        f"/api/v1/essays/{essay['id']}/versions/{version['id']}", headers=headers
    ).json()["data"]
    assert detail["plain_text"] == "Detail content."
    assert detail["content_json"]["content"][0]["content"][0]["text"] == "Detail content."
    assert detail["content_hash"]


def test_restore_copies_snapshot_and_records_event(client, db):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    assert (
        save_document(
            client, headers, essay["id"], base_revision=1, paragraphs=("Original draft.",)
        ).status_code
        == 200
    )
    snapshot = _snapshot(client, headers, essay["id"], 2).json()["data"]
    assert (
        save_document(
            client, headers, essay["id"], base_revision=2, paragraphs=("Later edits.",)
        ).status_code
        == 200
    )

    response = client.post(
        f"/api/v1/essays/{essay['id']}/restore",
        json={"version_id": snapshot["id"], "base_revision": 3},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["server_revision"] == 4
    assert data["restored_version_id"] == snapshot["id"]

    working = client.get(f"/api/v1/essays/{essay['id']}/working-document", headers=headers).json()[
        "data"
    ]
    assert working["plain_text"] == "Original draft."
    assert working["word_count"] == 2

    # Source snapshot is untouched (immutability invariant).
    source = client.get(
        f"/api/v1/essays/{essay['id']}/versions/{snapshot['id']}", headers=headers
    ).json()["data"]
    assert source["plain_text"] == "Original draft."
    assert source["source_revision"] == 2

    events = list(db.execute(select(EssayEditEvent)).scalars())
    assert len(events) == 1
    event = events[0]
    assert event.event_type == "restore"
    assert event.actor_type == "user"
    assert event.from_server_revision == 3
    assert event.to_server_revision == 4
    assert event.from_version_id == uuid.UUID(snapshot["id"])
    assert event.before_text == "Later edits."
    assert event.after_text == "Original draft."
    assert event.event_metadata == {"restored_version_id": snapshot["id"]}


def test_restore_conflict_leaves_everything_unchanged(client, db):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    assert save_document(client, headers, essay["id"], base_revision=1).status_code == 200
    snapshot = _snapshot(client, headers, essay["id"], 2).json()["data"]

    response = client.post(
        f"/api/v1/essays/{essay['id']}/restore",
        json={"version_id": snapshot["id"], "base_revision": 99},
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "WORKING_DOCUMENT_CONFLICT"

    working = client.get(f"/api/v1/essays/{essay['id']}/working-document", headers=headers).json()[
        "data"
    ]
    assert working["server_revision"] == 2
    assert db.execute(select(EssayEditEvent)).scalars().first() is None


def test_restore_original_snapshot_empties_document(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    assert save_document(client, headers, essay["id"], base_revision=1).status_code == 200

    response = client.post(
        f"/api/v1/essays/{essay['id']}/restore",
        json={"version_id": essay["original_version_id"], "base_revision": 2},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    working = client.get(f"/api/v1/essays/{essay['id']}/working-document", headers=headers).json()[
        "data"
    ]
    assert working["plain_text"] == ""
    assert working["server_revision"] == 3


def test_restore_foreign_version_not_found(client):
    owner = auth_headers(client, "ver-owner@example.com")
    other = auth_headers(client, "ver-other@example.com")
    essay_a = create_essay(client, owner)
    essay_b = create_essay(client, other)
    version_b = _snapshot(client, other, essay_b["id"], 1).json()["data"]

    response = client.post(
        f"/api/v1/essays/{essay_a['id']}/restore",
        json={"version_id": version_b["id"], "base_revision": 1},
        headers=owner,
    )
    assert response.status_code == 404


def test_versions_isolated_between_users(client):
    owner = auth_headers(client, "iso-owner@example.com")
    intruder = auth_headers(client, "iso-intruder@example.com")
    essay = create_essay(client, owner)
    version = _snapshot(client, owner, essay["id"], 1).json()["data"]

    assert client.get(f"/api/v1/essays/{essay['id']}/versions", headers=intruder).status_code == 404
    assert (
        client.get(
            f"/api/v1/essays/{essay['id']}/versions/{version['id']}", headers=intruder
        ).status_code
        == 404
    )
    assert _snapshot(client, intruder, essay["id"], 1).status_code == 404
    assert (
        client.post(
            f"/api/v1/essays/{essay['id']}/restore",
            json={"version_id": version["id"], "base_revision": 1},
            headers=intruder,
        ).status_code
        == 404
    )


def test_idempotent_snapshot_replays_without_duplicate(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    assert save_document(client, headers, essay["id"], base_revision=1).status_code == 200
    headers_with_key = {**headers, "Idempotency-Key": "snap-key-1"}

    first = _snapshot(client, headers_with_key, essay["id"], 2)
    second = _snapshot(client, headers_with_key, essay["id"], 2)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["data"]["id"] == second.json()["data"]["id"]

    versions = client.get(f"/api/v1/essays/{essay['id']}/versions", headers=headers).json()["data"]
    assert len(versions["items"]) == 2  # original + one checkpoint


def test_idempotency_key_reuse_with_different_payload_rejected(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    headers_with_key = {**headers, "Idempotency-Key": "snap-key-2"}

    assert _snapshot(client, headers_with_key, essay["id"], 1).status_code == 201
    conflict = _snapshot(client, headers_with_key, essay["id"], 1, label="Different")
    assert conflict.status_code == 422
    assert conflict.json()["error"]["code"] == "VALIDATION_ERROR"


def test_snapshot_without_key_is_not_deduplicated(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)

    assert _snapshot(client, headers, essay["id"], 1).status_code == 201
    assert _snapshot(client, headers, essay["id"], 1).status_code == 201
    versions = client.get(f"/api/v1/essays/{essay['id']}/versions", headers=headers).json()["data"]
    assert len(versions["items"]) == 3
