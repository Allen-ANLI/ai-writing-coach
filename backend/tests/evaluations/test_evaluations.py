"""Evaluation/rewrite integration tests (Slice 7).

Background processing runs synchronously under TestClient, so queued work is
complete by the time the 202 response returns. The mock LLM keeps everything
deterministic; band normalization and acceptance are asserted exactly.
"""

import uuid
from decimal import Decimal

from essay_helpers import auth_headers, create_essay, save_document
from sqlalchemy import select

from app.ai import llm
from app.ai.providers.base import LlmUsage
from app.ai.schemas import IeltsTask2EvaluationResult
from app.core.exceptions import ApiError
from app.modules.analytics.models import AiUsageLog
from app.modules.essays.models import EssayEditEvent
from app.modules.evaluations.models import EssayEvaluation, EssayRewrite


def _essay_with_version(client, headers, writing_type="ielts_task2", text="Some essay text."):
    essay = create_essay(client, headers, writing_type=writing_type)
    response = save_document(client, headers, essay["id"], base_revision=1, paragraphs=(text,))
    assert response.status_code == 200, response.text
    snapshot = client.post(
        f"/api/v1/essays/{essay['id']}/snapshots",
        json={"version_type": "checkpoint", "source_revision": 2},
        headers=headers,
    )
    assert snapshot.status_code == 201, snapshot.text
    return essay, snapshot.json()["data"]


def _queue_evaluation(client, headers, essay_id, version_id, **overrides):
    payload = {"version_id": version_id, "evaluation_type": "ielts", "task_type": "task2"}
    payload.update(overrides)
    return client.post(f"/api/v1/essays/{essay_id}/evaluations", json=payload, headers=headers)


def test_ielts_evaluation_completes_with_estimate(client):
    headers = auth_headers(client)
    essay, version = _essay_with_version(client, headers)

    response = _queue_evaluation(client, headers, essay["id"], version["id"])
    assert response.status_code == 202, response.text
    evaluation_id = response.json()["data"]["evaluation_id"]
    assert response.json()["data"]["status"] == "queued"

    detail = client.get(f"/api/v1/evaluations/{evaluation_id}", headers=headers)
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["status"] == "completed"
    assert data["is_estimate"] is True
    assert data["overall_band"] is not None
    assert set(data["criteria_scores"]) == {
        "task_response",
        "coherence_cohesion",
        "lexical_resource",
        "grammatical_range_accuracy",
    }
    assert data["feedback_json"]["overall_feedback"]
    assert data["model_name"] == "mock-deterministic-v1"
    assert data["prompt_version"] == "v1"
    assert data["version_id"] == version["id"]


def test_task1_uses_task_achievement_schema(client):
    headers = auth_headers(client)
    essay, version = _essay_with_version(client, headers, writing_type="ielts_task1")
    response = _queue_evaluation(client, headers, essay["id"], version["id"], task_type="task1")
    assert response.status_code == 202
    data = client.get(
        f"/api/v1/evaluations/{response.json()['data']['evaluation_id']}", headers=headers
    ).json()["data"]
    assert "task_achievement" in data["criteria_scores"]
    assert "task_response" not in data["criteria_scores"]


def test_general_evaluation_has_three_dimensions(client):
    headers = auth_headers(client)
    essay, version = _essay_with_version(client, headers, writing_type="free_writing")
    response = _queue_evaluation(
        client, headers, essay["id"], version["id"], evaluation_type="general", task_type=None
    )
    assert response.status_code == 202
    data = client.get(
        f"/api/v1/evaluations/{response.json()['data']['evaluation_id']}", headers=headers
    ).json()["data"]
    assert set(data["criteria_scores"]) == {"content", "organization", "language"}
    assert data["task_type"] is None


def test_evaluation_type_validation(client):
    headers = auth_headers(client)
    essay, version = _essay_with_version(client, headers)

    response = _queue_evaluation(client, headers, essay["id"], version["id"], task_type=None)
    assert response.status_code == 422

    response = _queue_evaluation(
        client, headers, essay["id"], version["id"], evaluation_type="general"
    )
    assert response.status_code == 422

    response = _queue_evaluation(client, headers, essay["id"], str(uuid.uuid4()))
    assert response.status_code == 404


def test_version_must_belong_to_same_essay(client):
    headers = auth_headers(client)
    essay_a, _ = _essay_with_version(client, headers)
    essay_b, version_b = _essay_with_version(client, headers)
    response = _queue_evaluation(client, headers, essay_a["id"], version_b["id"])
    assert response.status_code == 404


def test_task_type_must_match_bank_question(client):
    headers = auth_headers(client)
    questions = client.get(
        "/api/v1/ielts/questions", params={"task_type": "task1", "limit": 1}, headers=headers
    ).json()["data"]["items"]
    essay = create_essay(
        client, headers, writing_type="ielts_task1", question_id=questions[0]["id"]
    )
    snapshot = client.post(
        f"/api/v1/essays/{essay['id']}/snapshots",
        json={"version_type": "checkpoint", "source_revision": 1},
        headers=headers,
    ).json()["data"]

    response = _queue_evaluation(client, headers, essay["id"], snapshot["id"], task_type="task2")
    assert response.status_code == 422
    response = _queue_evaluation(client, headers, essay["id"], snapshot["id"], task_type="task1")
    assert response.status_code == 202


def test_bands_normalized_and_overall_computed_server_side(client, monkeypatch):
    def fake_call_llm(*, system, user, response_model):
        result = IeltsTask2EvaluationResult(
            task_response={"band": 6.3, "feedback": "ok"},
            coherence_cohesion={"band": 6.7, "feedback": "ok"},
            lexical_resource={"band": 7.1, "feedback": "ok"},
            grammatical_range_accuracy={"band": 5.9, "feedback": "ok"},
            overall_feedback="整体不错。",
            strengths=["观点清晰"],
            improvements=["增加连接词"],
        )
        usage = LlmUsage(
            provider="mock",
            model_name="fake",
            input_tokens=1,
            output_tokens=1,
            latency_ms=1,
            estimated_cost=0.0,
        )
        return result, usage

    monkeypatch.setattr(llm, "call_llm", fake_call_llm)
    headers = auth_headers(client)
    essay, version = _essay_with_version(client, headers)
    response = _queue_evaluation(client, headers, essay["id"], version["id"])
    data = client.get(
        f"/api/v1/evaluations/{response.json()['data']['evaluation_id']}", headers=headers
    ).json()["data"]

    bands = {k: v["band"] for k, v in data["criteria_scores"].items()}
    assert bands == {
        "task_response": 6.5,
        "coherence_cohesion": 6.5,
        "lexical_resource": 7.0,
        "grammatical_range_accuracy": 6.0,
    }
    assert Decimal(str(data["overall_band"])) == Decimal("6.5")


def test_llm_failure_marks_evaluation_failed(client, monkeypatch):
    def failing_call_llm(**kwargs):
        raise ApiError(502, "LLM_PROVIDER_ERROR", "The AI service failed.")

    monkeypatch.setattr(llm, "call_llm", failing_call_llm)
    headers = auth_headers(client)
    essay, version = _essay_with_version(client, headers)
    response = _queue_evaluation(client, headers, essay["id"], version["id"])
    assert response.status_code == 202
    data = client.get(
        f"/api/v1/evaluations/{response.json()['data']['evaluation_id']}", headers=headers
    ).json()["data"]
    assert data["status"] == "failed"
    assert data["error_message"]
    assert data["overall_band"] is None


def test_usage_logged_for_evaluation(client, db):
    headers = auth_headers(client)
    essay, version = _essay_with_version(client, headers)
    _queue_evaluation(client, headers, essay["id"], version["id"])
    logs = list(db.execute(select(AiUsageLog)).scalars())
    assert len(logs) == 1
    assert logs[0].feature == "ielts_evaluate_task2"
    assert logs[0].status == "success"
    assert logs[0].prompt_version == "v1"


def test_list_and_ownership(client):
    headers_a = auth_headers(client, email="eval-a@example.com")
    headers_b = auth_headers(client, email="eval-b@example.com")
    essay, version = _essay_with_version(client, headers_a)
    evaluation_id = _queue_evaluation(client, headers_a, essay["id"], version["id"]).json()["data"][
        "evaluation_id"
    ]

    listing = client.get(f"/api/v1/essays/{essay['id']}/evaluations", headers=headers_a)
    assert listing.status_code == 200
    assert len(listing.json()["data"]["items"]) == 1

    assert client.get(f"/api/v1/evaluations/{evaluation_id}", headers=headers_b).status_code == 404
    response = client.delete(f"/api/v1/evaluations/{evaluation_id}", headers=headers_b)
    assert response.status_code == 404
    response = client.get(f"/api/v1/essays/{essay['id']}/evaluations", headers=headers_b)
    assert response.status_code == 404


def test_idempotent_queue_replays_without_duplicate(client, db):
    headers = auth_headers(client)
    essay, version = _essay_with_version(client, headers)
    payload = {"version_id": version["id"], "evaluation_type": "ielts", "task_type": "task2"}
    key = {"Idempotency-Key": "eval-key-1"}

    first = client.post(
        f"/api/v1/essays/{essay['id']}/evaluations", json=payload, headers={**headers, **key}
    )
    second = client.post(
        f"/api/v1/essays/{essay['id']}/evaluations", json=payload, headers={**headers, **key}
    )
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["data"]["evaluation_id"] == second.json()["data"]["evaluation_id"]
    assert len(list(db.execute(select(EssayEvaluation)).scalars())) == 1

    different = client.post(
        f"/api/v1/essays/{essay['id']}/evaluations",
        json={**payload, "task_type": "task1"},
        headers={**headers, **key},
    )
    assert different.status_code == 422


def _completed_evaluation(client, headers):
    essay, version = _essay_with_version(client, headers)
    evaluation_id = _queue_evaluation(client, headers, essay["id"], version["id"]).json()["data"][
        "evaluation_id"
    ]
    return essay, version, evaluation_id


def test_rewrite_completes_and_binds_source_version(client):
    headers = auth_headers(client)
    essay, version, evaluation_id = _completed_evaluation(client, headers)

    response = client.post(
        f"/api/v1/evaluations/{evaluation_id}/rewrite",
        json={"modification_level": "level_2"},
        headers=headers,
    )
    assert response.status_code == 202, response.text
    rewrite_id = response.json()["data"]["rewrite_id"]

    data = client.get(f"/api/v1/rewrites/{rewrite_id}", headers=headers).json()["data"]
    assert data["status"] == "completed"
    assert data["source_version_id"] == version["id"]
    assert data["result_plain_text"]
    assert data["change_summary"]
    assert data["result_version_id"] is None


def test_rewrite_requires_completed_evaluation(client, db):
    headers = auth_headers(client)
    essay, version, evaluation_id = _completed_evaluation(client, headers)
    evaluation = db.get(EssayEvaluation, uuid.UUID(evaluation_id))
    evaluation.status = "queued"
    db.commit()

    response = client.post(
        f"/api/v1/evaluations/{evaluation_id}/rewrite",
        json={"modification_level": "level_1"},
        headers=headers,
    )
    assert response.status_code == 409


def test_rewrite_level_validation(client):
    headers = auth_headers(client)
    _, _, evaluation_id = _completed_evaluation(client, headers)
    response = client.post(
        f"/api/v1/evaluations/{evaluation_id}/rewrite",
        json={"modification_level": "level_5"},
        headers=headers,
    )
    assert response.status_code == 422


def _ready_rewrite(client, headers):
    essay, version, evaluation_id = _completed_evaluation(client, headers)
    rewrite_id = client.post(
        f"/api/v1/evaluations/{evaluation_id}/rewrite",
        json={"modification_level": "level_3"},
        headers=headers,
    ).json()["data"]["rewrite_id"]
    return essay, version, evaluation_id, rewrite_id


def test_accept_rewrite_is_atomic_and_server_authoritative(client, db):
    headers = auth_headers(client)
    essay, version, _, rewrite_id = _ready_rewrite(client, headers)
    rewrite = client.get(f"/api/v1/rewrites/{rewrite_id}", headers=headers).json()["data"]
    document = client.get(f"/api/v1/essays/{essay['id']}/working-document", headers=headers).json()[
        "data"
    ]

    response = client.post(
        f"/api/v1/rewrites/{rewrite_id}/accept",
        json={"base_revision": document["server_revision"], "client_revision": 99},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["server_revision"] == document["server_revision"] + 1

    updated = client.get(f"/api/v1/essays/{essay['id']}/working-document", headers=headers).json()[
        "data"
    ]
    assert updated["plain_text"] == rewrite["result_plain_text"]

    versions = client.get(f"/api/v1/essays/{essay['id']}/versions", headers=headers).json()["data"][
        "items"
    ]
    ai_versions = [v for v in versions if v["version_type"] == "ai_rewrite"]
    assert len(ai_versions) == 1
    assert ai_versions[0]["id"] == data["result_version_id"]

    events = list(db.execute(select(EssayEditEvent)).scalars())
    accept_events = [e for e in events if e.event_type == "accept_rewrite"]
    assert len(accept_events) == 1
    assert accept_events[0].actor_type == "ai_accept"
    assert str(accept_events[0].rewrite_id) == rewrite_id

    original = [v for v in versions if v["version_type"] == "original"][0]
    original_detail = client.get(
        f"/api/v1/essays/{essay['id']}/versions/{original['id']}", headers=headers
    ).json()["data"]
    assert original_detail["plain_text"] == ""

    stored = db.get(EssayRewrite, uuid.UUID(rewrite_id))
    assert str(stored.result_version_id) == data["result_version_id"]


def test_accept_revision_conflict(client):
    headers = auth_headers(client)
    _, _, _, rewrite_id = _ready_rewrite(client, headers)
    response = client.post(
        f"/api/v1/rewrites/{rewrite_id}/accept",
        json={"base_revision": 1, "client_revision": 1},
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "WORKING_DOCUMENT_CONFLICT"


def test_accept_duplicate_and_not_ready(client, db):
    headers = auth_headers(client)
    essay, _, _, rewrite_id = _ready_rewrite(client, headers)
    document = client.get(f"/api/v1/essays/{essay['id']}/working-document", headers=headers).json()[
        "data"
    ]
    payload = {"base_revision": document["server_revision"], "client_revision": 1}
    assert (
        client.post(
            f"/api/v1/rewrites/{rewrite_id}/accept", json=payload, headers=headers
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/rewrites/{rewrite_id}/accept", json=payload, headers=headers
        ).status_code
        == 409
    )

    evaluation = db.execute(select(EssayEvaluation)).scalars().first()
    queued = EssayRewrite(
        evaluation_id=evaluation.id,
        source_version_id=evaluation.version_id,
        modification_level="level_1",
        status="queued",
    )
    db.add(queued)
    db.commit()
    response = client.post(f"/api/v1/rewrites/{queued.id}/accept", json=payload, headers=headers)
    assert response.status_code == 409


def test_accept_cross_user_404(client):
    headers_a = auth_headers(client, email="rw-a@example.com")
    headers_b = auth_headers(client, email="rw-b@example.com")
    _, _, _, rewrite_id = _ready_rewrite(client, headers_a)
    response = client.post(
        f"/api/v1/rewrites/{rewrite_id}/accept",
        json={"base_revision": 2, "client_revision": 1},
        headers=headers_b,
    )
    assert response.status_code == 404


def test_delete_evaluation_cascades_rewrites_keeps_versions(client, db):
    headers = auth_headers(client)
    essay, _, evaluation_id, rewrite_id = _ready_rewrite(client, headers)
    response = client.delete(f"/api/v1/evaluations/{evaluation_id}", headers=headers)
    assert response.status_code == 204
    assert client.get(f"/api/v1/rewrites/{rewrite_id}", headers=headers).status_code == 404
    assert db.get(EssayRewrite, uuid.UUID(rewrite_id)) is None
    versions = client.get(f"/api/v1/essays/{essay['id']}/versions", headers=headers).json()["data"][
        "items"
    ]
    assert len(versions) >= 2
