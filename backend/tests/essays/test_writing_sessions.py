"""Writing session integration tests on real PostgreSQL (API Spec §5, SD §10).

Covers mode-derived feature flags, exam config validation, one-active-session
rule, ownership isolation, atomic submit (final snapshot, shared-original case,
revision conflict, edit event), and idempotent submit.
"""

import uuid

from essay_helpers import auth_headers, create_essay, save_document
from sqlalchemy import select

from app.modules.essays.models import EssayEditEvent


def _start(client, headers, essay_id, mode="assisted", activity_type="practice", exam_config=None):
    payload = {"mode": mode, "activity_type": activity_type}
    if exam_config is not None:
        payload["exam_config"] = exam_config
    return client.post(f"/api/v1/essays/{essay_id}/sessions", json=payload, headers=headers)


MOCK_EXAM = {"exam_type": "IELTS", "task_type": "task2", "duration_minutes": 40, "word_limit": 250}


def test_assisted_session_enables_realtime_features(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)

    response = _start(client, headers, essay["id"])
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["mode"] == "assisted"
    assert data["status"] == "active"
    features = data["enabled_features"]
    assert features["realtime_grammar"] is True
    assert features["llm_assistance"] is True
    assert features["chinese_to_english"] is True
    assert features["expression_recommendations"] is True
    assert features["ghost_text"] is True
    assert features["autosave"] is True
    assert features["post_submission_evaluation"] is True


def test_independent_session_disables_realtime_features(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)

    response = _start(client, headers, essay["id"], mode="independent")
    assert response.status_code == 201, response.text
    features = response.json()["data"]["enabled_features"]
    for key in (
        "realtime_grammar",
        "llm_assistance",
        "chinese_to_english",
        "expression_recommendations",
        "ghost_text",
        "paragraph_analysis",
    ):
        assert features[key] is False, key
    assert features["autosave"] is True
    assert features["post_submission_evaluation"] is True


def test_mock_exam_requires_config_and_sets_deadline(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)

    missing = _start(client, headers, essay["id"], mode="independent", activity_type="mock_exam")
    assert missing.status_code == 422

    response = _start(
        client,
        headers,
        essay["id"],
        mode="independent",
        activity_type="mock_exam",
        exam_config=MOCK_EXAM,
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["deadline_at"] is not None
    assert data["exam_config"]["duration_minutes"] == 40


def test_exam_config_rejected_for_non_exam_sessions(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)

    response = _start(client, headers, essay["id"], exam_config=MOCK_EXAM)
    assert response.status_code == 422


def test_only_one_active_session_per_essay(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    assert _start(client, headers, essay["id"]).status_code == 201

    second = _start(client, headers, essay["id"])
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "RESOURCE_ALREADY_EXISTS"


def test_session_list_and_detail(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    created = _start(client, headers, essay["id"]).json()["data"]

    listing = client.get(f"/api/v1/essays/{essay['id']}/sessions", headers=headers)
    assert listing.status_code == 200
    items = listing.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["id"] == created["id"]
    assert "enabled_features" in items[0]

    detail = client.get(f"/api/v1/writing-sessions/{created['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["id"] == created["id"]


def test_sessions_isolated_between_users(client):
    owner = auth_headers(client, "sess-owner@example.com")
    intruder = auth_headers(client, "sess-intruder@example.com")
    essay = create_essay(client, owner)
    session = _start(client, owner, essay["id"]).json()["data"]

    assert client.get(f"/api/v1/essays/{essay['id']}/sessions", headers=intruder).status_code == 404
    assert _start(client, intruder, essay["id"]).status_code == 404
    assert (
        client.get(f"/api/v1/writing-sessions/{session['id']}", headers=intruder).status_code == 404
    )
    assert (
        client.patch(
            f"/api/v1/writing-sessions/{session['id']}",
            json={"status": "cancelled"},
            headers=intruder,
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/writing-sessions/{session['id']}/submit",
            json={"expected_server_revision": 1},
            headers=intruder,
        ).status_code
        == 404
    )


def test_cancel_session_frees_the_essay(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    session = _start(client, headers, essay["id"]).json()["data"]

    cancelled = client.patch(
        f"/api/v1/writing-sessions/{session['id']}",
        json={"status": "cancelled"},
        headers=headers,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "cancelled"
    assert _start(client, headers, essay["id"]).status_code == 201


def test_submit_creates_final_snapshot_and_event(client, db):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    session = _start(client, headers, essay["id"]).json()["data"]
    assert (
        save_document(
            client, headers, essay["id"], base_revision=1, paragraphs=("Final essay text.",)
        ).status_code
        == 200
    )

    response = client.post(
        f"/api/v1/writing-sessions/{session['id']}/submit",
        json={"expected_server_revision": 2},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["status"] == "submitted"
    assert data["shared_original"] is False
    assert data["server_revision"] == 2

    detail = client.get(f"/api/v1/essays/{essay['id']}", headers=headers).json()["data"]
    assert detail["final_version_id"] == data["final_version_id"]

    final = client.get(
        f"/api/v1/essays/{essay['id']}/versions/{data['final_version_id']}", headers=headers
    ).json()["data"]
    assert final["version_type"] == "final"
    assert final["plain_text"] == "Final essay text."

    events = list(db.execute(select(EssayEditEvent)).scalars())
    assert len(events) == 1
    assert events[0].event_type == "submit"
    assert events[0].to_version_id == uuid.UUID(data["final_version_id"])
    assert events[0].event_metadata["session_id"] == session["id"]

    # Session is no longer active; resubmission is rejected.
    again = client.post(
        f"/api/v1/writing-sessions/{session['id']}/submit",
        json={"expected_server_revision": 2},
        headers=headers,
    )
    assert again.status_code == 400


def test_submit_shares_original_when_content_unchanged(client, db):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    session = _start(client, headers, essay["id"], mode="independent").json()["data"]

    response = client.post(
        f"/api/v1/writing-sessions/{session['id']}/submit",
        json={"expected_server_revision": 1},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["shared_original"] is True
    assert data["final_version_id"] == essay["original_version_id"]

    versions = client.get(f"/api/v1/essays/{essay['id']}/versions", headers=headers).json()["data"]
    assert len(versions["items"]) == 1  # no extra snapshot created


def test_submit_revision_conflict_no_partial_write(client, db):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    session = _start(client, headers, essay["id"]).json()["data"]
    assert save_document(client, headers, essay["id"], base_revision=1).status_code == 200

    response = client.post(
        f"/api/v1/writing-sessions/{session['id']}/submit",
        json={"expected_server_revision": 1},
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "WORKING_DOCUMENT_CONFLICT"

    detail = client.get(f"/api/v1/essays/{essay['id']}", headers=headers).json()["data"]
    assert detail["final_version_id"] is None
    refreshed = client.get(f"/api/v1/writing-sessions/{session['id']}", headers=headers).json()[
        "data"
    ]
    assert refreshed["status"] == "active"
    assert db.execute(select(EssayEditEvent)).scalars().first() is None


def test_submit_idempotent_replay(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    session = _start(client, headers, essay["id"]).json()["data"]
    assert save_document(client, headers, essay["id"], base_revision=1).status_code == 200
    headers_with_key = {**headers, "Idempotency-Key": "submit-key-1"}

    first = client.post(
        f"/api/v1/writing-sessions/{session['id']}/submit",
        json={"expected_server_revision": 2},
        headers=headers_with_key,
    )
    second = client.post(
        f"/api/v1/writing-sessions/{session['id']}/submit",
        json={"expected_server_revision": 2},
        headers=headers_with_key,
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["data"] == second.json()["data"]

    versions = client.get(f"/api/v1/essays/{essay['id']}/versions", headers=headers).json()["data"]
    assert len(versions["items"]) == 2  # original + one final


def test_patch_exam_config_updates_deadline(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    session = _start(
        client,
        headers,
        essay["id"],
        mode="independent",
        activity_type="mock_exam",
        exam_config=MOCK_EXAM,
    ).json()["data"]

    updated_config = {**MOCK_EXAM, "duration_minutes": 60}
    response = client.patch(
        f"/api/v1/writing-sessions/{session['id']}",
        json={"exam_config": updated_config},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["exam_config"]["duration_minutes"] == 60
    assert data["deadline_at"] > session["deadline_at"]


def test_same_owner_enforced_at_database_level(client, db):
    """The composite FK rejects a session whose user differs from the essay owner."""
    from app.modules.writing_sessions.models import WritingSession

    owner = auth_headers(client, "fk-owner@example.com")
    other = auth_headers(client, "fk-other@example.com")
    essay = create_essay(client, owner)
    other_user_id = client.get("/api/v1/users/me", headers=other).json()["data"]["id"]

    import pytest
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        db.add(
            WritingSession(
                essay_id=uuid.UUID(essay["id"]),
                user_id=uuid.UUID(other_user_id),
                mode="assisted",
                activity_type="practice",
            )
        )
        db.commit()
    db.rollback()
