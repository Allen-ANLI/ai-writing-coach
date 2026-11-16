"""Ghost-guidance progress judgment tests (ADR-025). Mock LLM keeps judgments
deterministic; provider-failure degradation and caching are covered here.
"""

from essay_helpers import auth_headers, create_essay

from app.ai import llm
from app.ai.providers.base import LlmUsage
from app.ai.schemas import GhostProgressResult
from app.core.exceptions import ApiError
from app.modules.outlines import chat


def _usage() -> LlmUsage:
    return LlmUsage(
        provider="mock",
        model_name="mock-deterministic-v1",
        input_tokens=5,
        output_tokens=5,
        latency_ms=3,
        estimated_cost=0.0,
    )


def _progress(client, headers, essay_id, **overrides):
    payload = {
        "sentence": "Public transport should be free in big cities.",
        "idea_index": 0,
        "idea": "表明立场：公共交通免费",
        **overrides,
    }
    return client.post(f"/api/v1/essays/{essay_id}/planner/progress", json=payload, headers=headers)


def _patch(monkeypatch, fulfilled: bool):
    def fake_call_llm(*, system, user, response_model):
        assert response_model is GhostProgressResult
        return GhostProgressResult(fulfilled=fulfilled, reason=None), _usage()

    monkeypatch.setattr(llm, "call_llm", fake_call_llm)


def test_fulfilled_judgment_logged(client, monkeypatch, db):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    _patch(monkeypatch, True)

    response = _progress(client, headers, essay["id"])
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data == {"fulfilled": True, "reason": None, "degraded": False}

    from app.modules.analytics.models import AiUsageLog

    logs = db.query(AiUsageLog).filter(AiUsageLog.feature == "ghost_progress").all()
    assert len(logs) == 1
    assert logs[0].status == "success"
    assert logs[0].prompt_version == "v3"


def test_not_fulfilled_keeps_guidance(client, monkeypatch):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    _patch(monkeypatch, False)

    data = _progress(client, headers, essay["id"]).json()["data"]
    assert data["fulfilled"] is False
    assert data["degraded"] is False


def test_judgment_cached_no_second_call(client, monkeypatch):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    calls = []

    def fake_call_llm(*, system, user, response_model):
        calls.append(user)
        return GhostProgressResult(fulfilled=True, reason=None), _usage()

    monkeypatch.setattr(llm, "call_llm", fake_call_llm)
    first = _progress(client, headers, essay["id"]).json()["data"]
    second = _progress(client, headers, essay["id"]).json()["data"]
    assert first == second
    assert len(calls) == 1


def test_provider_failure_degrades_to_advance(client, monkeypatch):
    headers = auth_headers(client)
    essay = create_essay(client, headers)

    def failing_call_llm(**kwargs):
        raise ApiError(502, "LLM_PROVIDER_ERROR", "The AI service failed.")

    monkeypatch.setattr(llm, "call_llm", failing_call_llm)
    data = _progress(client, headers, essay["id"], idea_index=7).json()["data"]
    assert data == {"fulfilled": True, "reason": None, "degraded": True}


def test_quota_guard_blocks(client, monkeypatch):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    from app.modules.billing import service as billing_service

    def deny(db, user_id):
        raise ApiError(429, "QUOTA_EXCEEDED", "AI quota exceeded.")

    monkeypatch.setattr(billing_service, "guard_ai_call", deny)
    assert _progress(client, headers, essay["id"], idea_index=9).status_code == 429


def test_ownership_and_validation(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    other = auth_headers(client, email="other-progress@example.com")
    assert _progress(client, other, essay["id"]).status_code == 404
    assert (
        client.post(
            f"/api/v1/essays/{essay['id']}/planner/progress",
            json={"sentence": "", "idea_index": 0, "idea": "x"},
            headers=headers,
        ).status_code
        == 422
    )


def test_cache_is_scoped_per_user(client, monkeypatch):
    _patch(monkeypatch, True)
    a = auth_headers(client, email="progress-a@example.com")
    b = auth_headers(client, email="progress-b@example.com")
    ea = create_essay(client, a)
    eb = create_essay(client, b)
    assert _progress(client, a, ea["id"]).status_code == 200
    # Same sentence/idea, different user: must not leak cached judgments
    # across accounts (cache key includes user id).
    assert _progress(client, b, eb["id"]).status_code == 200
    assert (user_key_scope := chat._PROGRESS_CACHE) is not None
    assert len({k[0] for k in user_key_scope}) >= 2
