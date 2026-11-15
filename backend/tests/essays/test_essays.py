"""Essay CRUD integration tests on real PostgreSQL.

Covers atomic creation, pagination, ownership isolation, title updates, soft
delete, deleted-resource access, invalid question IDs, and transaction
rollback.
"""

import hashlib
import uuid

import pytest
from essay_helpers import auth_headers, create_essay
from sqlalchemy.exc import IntegrityError

from app.modules.essays import service
from app.modules.essays.models import Essay, EssayVersion, EssayWorkingDocument


def test_create_essay_atomically_creates_all_three_entities(client, db):
    headers = auth_headers(client)

    response = client.post(
        "/api/v1/essays",
        json={"writing_type": "ielts_task2", "title": "Atomic essay"},
        headers=headers,
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["title"] == "Atomic essay"
    assert data["writing_type"] == "ielts_task2"
    assert data["status"] == "active"
    assert data["original_version_id"] is not None
    assert data["working_document"]["server_revision"] == 1
    assert data["working_document"]["word_count"] == 0
    assert response.json()["meta"]["request_id"]

    essay = db.query(Essay).one()
    working = db.query(EssayWorkingDocument).one()
    version = db.query(EssayVersion).one()
    empty_hash = hashlib.sha256(b"").hexdigest()

    assert working.essay_id == essay.id
    assert working.content_json == {"type": "doc", "content": []}
    assert working.plain_text == ""
    assert working.content_hash == empty_hash
    assert version.essay_id == essay.id
    assert version.version_no == 1
    assert version.version_type == "original"
    assert version.source_revision == 1
    assert version.parent_version_id is None
    assert version.content_json == working.content_json
    assert version.content_hash == empty_hash
    assert version.created_by == essay.user_id
    assert essay.original_version_id == version.id


def test_create_essay_without_title_defaults_to_null(client):
    headers = auth_headers(client)
    response = client.post("/api/v1/essays", json={"writing_type": "free_writing"}, headers=headers)

    assert response.status_code == 201
    assert response.json()["data"]["title"] is None


def test_create_essay_requires_writing_type(client):
    headers = auth_headers(client)
    response = client.post("/api/v1/essays", json={"title": "x"}, headers=headers)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_essay_rejects_invalid_writing_type(client):
    headers = auth_headers(client)
    response = client.post("/api/v1/essays", json={"writing_type": "novel"}, headers=headers)

    assert response.status_code == 422


def test_create_essay_rejects_invalid_question_id(client):
    headers = auth_headers(client)
    response = client.post(
        "/api/v1/essays",
        json={"writing_type": "ielts_task1", "question_id": "not-a-uuid"},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_essay_rejects_unknown_question_id(client):
    # Slice 6 attached the IELTS FK: question_id must reference a published,
    # permitted bank question (happy path covered in tests/ielts).
    headers = auth_headers(client)
    question_id = str(uuid.uuid4())
    response = client.post(
        "/api/v1/essays",
        json={"writing_type": "ielts_task1", "question_id": question_id},
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_creation_rolls_back_when_snapshot_insert_fails(client, db, monkeypatch):
    headers = auth_headers(client)

    def sabotage(*args, **kwargs):
        raise RuntimeError("simulated snapshot failure")

    monkeypatch.setattr(service, "EssayVersion", sabotage)

    with pytest.raises(RuntimeError, match="simulated snapshot failure"):
        client.post("/api/v1/essays", json={"writing_type": "free_writing"}, headers=headers)

    # Essay and working document were flushed before the failure; the whole
    # transaction must have rolled back.
    assert db.query(Essay).count() == 0
    assert db.query(EssayWorkingDocument).count() == 0
    assert db.query(EssayVersion).count() == 0


def test_list_pagination_walks_all_pages_newest_first(client):
    headers = auth_headers(client)
    created = [create_essay(client, headers, title=f"Essay {i}") for i in range(5)]

    page1 = client.get("/api/v1/essays?limit=2", headers=headers).json()["data"]
    assert len(page1["items"]) == 2
    assert page1["next_cursor"]
    assert page1["items"][0]["id"] == created[4]["id"]

    page2 = client.get(
        f"/api/v1/essays?limit=2&cursor={page1['next_cursor']}", headers=headers
    ).json()["data"]
    assert [item["id"] for item in page2["items"]] == [created[2]["id"], created[1]["id"]]

    page3 = client.get(
        f"/api/v1/essays?limit=2&cursor={page2['next_cursor']}", headers=headers
    ).json()["data"]
    assert [item["id"] for item in page3["items"]] == [created[0]["id"]]
    assert page3["next_cursor"] is None


def test_list_rejects_invalid_cursor_and_limit(client):
    headers = auth_headers(client)

    assert client.get("/api/v1/essays?cursor=garbage", headers=headers).status_code == 422
    assert client.get("/api/v1/essays?limit=0", headers=headers).status_code == 422
    assert client.get("/api/v1/essays?limit=101", headers=headers).status_code == 422


def test_users_cannot_see_or_touch_each_others_essays(client):
    alice = auth_headers(client, email="alice@example.com")
    bob = auth_headers(client, email="bob@example.com")
    essay = create_essay(client, alice)

    assert client.get(f"/api/v1/essays/{essay['id']}", headers=bob).status_code == 404
    assert (
        client.patch(
            f"/api/v1/essays/{essay['id']}", json={"title": "hijack"}, headers=bob
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/essays/{essay['id']}", headers=bob).status_code == 404
    assert client.get("/api/v1/essays", headers=bob).json()["data"]["items"] == []
    # Alice still has hers.
    assert client.get(f"/api/v1/essays/{essay['id']}", headers=alice).status_code == 200


def test_update_title(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)

    response = client.patch(
        f"/api/v1/essays/{essay['id']}", json={"title": "Renamed"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["data"]["title"] == "Renamed"
    fetched = client.get(f"/api/v1/essays/{essay['id']}", headers=headers)
    assert fetched.json()["data"]["title"] == "Renamed"


def test_patch_rejects_unknown_fields_and_overlong_title(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)

    assert (
        client.patch(
            f"/api/v1/essays/{essay['id']}", json={"status": "archived"}, headers=headers
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/v1/essays/{essay['id']}", json={"title": "x" * 256}, headers=headers
        ).status_code
        == 422
    )


def test_soft_delete_hides_essay_but_keeps_row(client, db):
    headers = auth_headers(client)
    essay = create_essay(client, headers)

    assert client.delete(f"/api/v1/essays/{essay['id']}", headers=headers).status_code == 204

    row = db.get(Essay, uuid.UUID(essay["id"]))
    assert row is not None
    assert row.deleted_at is not None

    assert client.get(f"/api/v1/essays/{essay['id']}", headers=headers).status_code == 404
    assert (
        client.patch(
            f"/api/v1/essays/{essay['id']}", json={"title": "x"}, headers=headers
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/essays/{essay['id']}", headers=headers).status_code == 404
    assert client.get("/api/v1/essays", headers=headers).json()["data"]["items"] == []


def test_essay_endpoints_require_authentication(client):
    essay_id = uuid.uuid4()

    assert client.post("/api/v1/essays", json={"writing_type": "free_writing"}).status_code == 401
    assert client.get("/api/v1/essays").status_code == 401
    assert client.get(f"/api/v1/essays/{essay_id}").status_code == 401
    assert client.patch(f"/api/v1/essays/{essay_id}", json={"title": "x"}).status_code == 401
    assert client.delete(f"/api/v1/essays/{essay_id}").status_code == 401


def test_original_snapshot_is_not_mutated_by_metadata_ops(client, db):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    before = db.query(EssayVersion).one()
    before_id, before_hash = before.id, before.content_hash

    client.patch(f"/api/v1/essays/{essay['id']}", json={"title": "Changed"}, headers=headers)
    client.delete(f"/api/v1/essays/{essay['id']}", headers=headers)

    db.expire_all()
    after = db.query(EssayVersion).one()
    assert after.id == before_id
    assert after.content_hash == before_hash
    assert after.version_no == 1
    assert after.version_type == "original"
    # The ERD forbids a current_version_id pointer on essays.
    assert not hasattr(Essay, "current_version_id")


def test_version_parent_must_belong_to_same_essay(client, db):
    headers = auth_headers(client)
    essay_a = create_essay(client, headers, title="A")
    essay_b = create_essay(client, headers, title="B")
    version_a = db.query(EssayVersion).filter_by(essay_id=uuid.UUID(essay_a["id"])).one()

    rogue = EssayVersion(
        essay_id=uuid.UUID(essay_b["id"]),
        version_no=2,
        version_type="checkpoint",
        content_json={"type": "doc", "content": []},
        plain_text="",
        word_count=0,
        content_hash=hashlib.sha256(b"").hexdigest(),
        source_revision=1,
        parent_version_id=version_a.id,
        created_by=version_a.created_by,
    )
    db.add(rogue)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
