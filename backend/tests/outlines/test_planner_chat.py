"""Conversational planner integration tests (ADR-024). Mock LLM keeps turns
deterministic; real-provider behavior is verified by scripts/eval_ai.py.
"""

import uuid

from essay_helpers import auth_headers, create_essay

from app.ai import llm
from app.ai.providers.base import LlmUsage
from app.ai.schemas import OutlineGenerationResult, PlannerChatResult
from app.core.exceptions import ApiError


def _usage() -> LlmUsage:
    return LlmUsage(
        provider="mock",
        model_name="mock-deterministic-v1",
        input_tokens=10,
        output_tokens=10,
        latency_ms=5,
        estimated_cost=0.0,
    )


def _outline_payload() -> OutlineGenerationResult:
    return OutlineGenerationResult.model_validate(
        {
            "thesis_statement": "Public transport should be free in large cities.",
            "sections": [
                {
                    "title": "开头",
                    "paragraphs": [
                        {"title": "引入话题", "sentence_ideas": ["背景：城市交通拥堵", "表明立场"]}
                    ],
                },
                {
                    "title": "结尾",
                    "paragraphs": [{"title": "总结", "sentence_ideas": ["重申论点", "展望未来"]}],
                },
            ],
        }
    )


def _patch_llm(monkeypatch, result: PlannerChatResult):
    def fake_call_llm(*, system, user, response_model):
        assert response_model is PlannerChatResult
        return result, _usage()

    monkeypatch.setattr(llm, "call_llm", fake_call_llm)


def _chat(client, headers, essay_id, message):
    return client.post(
        f"/api/v1/essays/{essay_id}/planner/chat", json={"message": message}, headers=headers
    )


def test_discuss_turn_stores_history(client, monkeypatch):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    _patch_llm(
        monkeypatch, PlannerChatResult(reply="你对话题持什么立场？", action="discuss", outline=None)
    )

    response = _chat(client, headers, essay["id"], "我想写公共交通")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["message"]["role"] == "assistant"
    assert data["message"]["content"] == "你对话题持什么立场？"
    assert data["outline"] is None

    history = client.get(f"/api/v1/essays/{essay['id']}/planner/messages", headers=headers)
    assert history.status_code == 200
    items = history.json()["data"]["items"]
    assert [m["role"] for m in items] == ["user", "assistant"]
    assert items[0]["content"] == "我想写公共交通"


def test_propose_creates_confirmable_draft(client, monkeypatch):
    headers = auth_headers(client)
    essay = create_essay(client, headers, writing_type="ielts_task2")
    _patch_llm(
        monkeypatch,
        PlannerChatResult(
            reply="我为你拟好了大纲，请确认。", action="propose", outline=_outline_payload()
        ),
    )

    response = _chat(client, headers, essay["id"], "我同意公共交通免费")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    outline = data["outline"]
    assert outline is not None
    assert outline["status"] == "draft"
    assert outline["thesis_statement"] == "Public transport should be free in large cities."
    assert data["message"]["outline_id"] == outline["id"]
    ideas = [n for n in outline["nodes"] if n["node_type"] == "sentence_idea"]
    assert any("立场" in n["title"] for n in ideas)

    confirm = client.post(f"/api/v1/outlines/{outline['id']}/confirm", headers=headers)
    assert confirm.status_code == 200
    assert confirm.json()["data"]["status"] == "confirmed"


def test_revise_confirm_archives_previous_plan(client, monkeypatch):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    _patch_llm(
        monkeypatch,
        PlannerChatResult(reply="第一版大纲。", action="propose", outline=_outline_payload()),
    )
    first = _chat(client, headers, essay["id"], "开始构思").json()["data"]["outline"]
    client.post(f"/api/v1/outlines/{first['id']}/confirm", headers=headers)

    revised = _outline_payload()
    revised.sections[0].title = "开头（让步段在前）"
    _patch_llm(
        monkeypatch,
        PlannerChatResult(reply="已按你的要求调整结构。", action="revise", outline=revised),
    )
    second = _chat(client, headers, essay["id"], "把第二段改成让步段").json()["data"]["outline"]
    assert second["id"] != first["id"]
    assert second["version_no"] == 2

    confirm = client.post(f"/api/v1/outlines/{second['id']}/confirm", headers=headers)
    assert confirm.status_code == 200

    listing = client.get(f"/api/v1/essays/{essay['id']}/outlines", headers=headers)
    statuses = {i["id"]: i["status"] for i in listing.json()["data"]["items"]}
    assert statuses[first["id"]] == "archived"
    assert statuses[second["id"]] == "confirmed"


def test_chat_ownership_isolated(client, monkeypatch):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    _patch_llm(monkeypatch, PlannerChatResult(reply="你好", action="discuss", outline=None))
    assert _chat(client, headers, essay["id"], "你好").status_code == 200

    other = auth_headers(client, email=f"other-{uuid.uuid4().hex[:8]}@example.com")
    assert _chat(client, other, essay["id"], "hi").status_code == 404
    assert (
        client.get(f"/api/v1/essays/{essay['id']}/planner/messages", headers=other).status_code
        == 404
    )


def test_llm_failure_records_usage_and_keeps_user_message(client, monkeypatch, db):
    headers = auth_headers(client)
    essay = create_essay(client, headers)

    def failing_call_llm(**kwargs):
        raise ApiError(502, "LLM_PROVIDER_ERROR", "The AI service failed.")

    monkeypatch.setattr(llm, "call_llm", failing_call_llm)
    response = _chat(client, headers, essay["id"], "触发失败")
    assert response.status_code == 502

    from app.modules.analytics.models import AiUsageLog

    logs = db.query(AiUsageLog).filter(AiUsageLog.feature == "planner_chat").all()
    assert len(logs) == 1
    assert logs[0].status == "error"

    items = client.get(f"/api/v1/essays/{essay['id']}/planner/messages", headers=headers).json()[
        "data"
    ]["items"]
    assert [m["role"] for m in items] == ["user"]


def test_quota_guard_blocks_before_llm(client, monkeypatch):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    called = []

    def fake_call_llm(**kwargs):
        called.append(True)
        raise AssertionError("LLM must not be called when quota is exceeded")

    monkeypatch.setattr(llm, "call_llm", fake_call_llm)
    from app.modules.billing import service as billing_service

    def deny(db, user_id):
        raise ApiError(429, "QUOTA_EXCEEDED", "AI quota exceeded.")

    monkeypatch.setattr(billing_service, "guard_ai_call", deny)
    response = _chat(client, headers, essay["id"], "你好")
    assert response.status_code == 429
    assert not called


def test_empty_message_rejected(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    assert _chat(client, headers, essay["id"], "   ").status_code == 422
