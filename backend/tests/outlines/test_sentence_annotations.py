"""ADR-037: per-sentence model-essay annotations (expressions + pattern).

Generated WITH the model essay (planner_chat v8 / model_essay_generate v4),
validated 1:1 against the English sentences with verbatim expression grounding,
expired together with the essay on outline edits, and served in outline
responses for the ghost-hint insight card. Mock LLM keeps turns deterministic.
"""

import re

from essay_helpers import auth_headers, create_essay
from sqlalchemy import select

from app.ai import llm
from app.ai.providers.base import LlmUsage
from app.ai.schemas import PlannerChatResult, SentenceAnnotation
from app.modules.analytics.models import AiUsageLog
from app.modules.outlines.service import validate_annotations


def _pattern() -> dict:
    return {"label": "简单句", "skeleton": "主语 + 动词 + 宾语", "explanation": "陈述事实。"}


def _annotation(expressions: list[str]) -> SentenceAnnotation:
    return SentenceAnnotation.model_validate(
        {
            "expressions": [
                {"text": t, "meaning": "释义", "usage": "用法"} for t in expressions
            ],
            "pattern": _pattern(),
        }
    )


# --- validate_annotations (pure) ---------------------------------------------


def test_validate_keeps_aligned_verbatim_annotations():
    essay = "I like apples. She likes pears."
    annotations = [
        _annotation(["like apples", "not present"]),
        _annotation(["likes pears"]),
    ]
    out = validate_annotations(annotations, essay)
    assert out is not None and len(out) == 2
    # Non-verbatim expression dropped; the grounded one survives.
    assert [e["text"] for e in out[0]["expressions"]] == ["like apples"]
    assert out[1]["pattern"]["skeleton"] == "主语 + 动词 + 宾语"


def test_validate_count_mismatch_degrades_to_none():
    essay = "One sentence. Two sentence. Three sentence."
    assert validate_annotations([_annotation(["One sentence"])], essay) is None


def test_validate_all_expressions_ungrounded_degrades_to_none():
    essay = "I like apples."
    assert validate_annotations([_annotation(["totally absent"])], essay) is None


def test_validate_empty_inputs():
    assert validate_annotations(None, "Some sentence.") is None
    assert validate_annotations([], "Some sentence.") is None
    assert validate_annotations([_annotation(["x"])], None) is None


# --- Integration (mock provider) ----------------------------------------------


def _chat_propose(client, headers, essay_id):
    response = client.post(
        f"/api/v1/essays/{essay_id}/planner/chat",
        json={"message": "我想写大城市公共交通应该免费"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    outline = response.json()["data"]["outline"]
    assert outline is not None
    return outline


def test_planner_propose_stores_grounded_annotations(client, db):
    headers = auth_headers(client)
    essay = create_essay(client, headers)

    outline = _chat_propose(client, headers, essay["id"])
    annotations = outline["model_essay_annotations"]
    assert annotations is not None
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", outline["model_essay"].strip()) if s]
    assert len(annotations) == len(sentences) == 3
    for sentence, annotation in zip(sentences, annotations, strict=True):
        assert annotation["expressions"]
        for expression in annotation["expressions"]:
            assert expression["text"].lower() in sentence.lower()
        assert annotation["pattern"]["label"]
        assert annotation["pattern"]["skeleton"]

    logs = list(
        db.execute(select(AiUsageLog).where(AiUsageLog.feature == "planner_chat")).scalars()
    )
    assert logs and logs[0].prompt_version == "v8"


def test_confirm_and_get_carry_annotations(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    outline = _chat_propose(client, headers, essay["id"])

    confirmed = client.post(f"/api/v1/outlines/{outline['id']}/confirm", headers=headers)
    assert confirmed.status_code == 200, confirmed.text
    detail = client.get(f"/api/v1/outlines/{outline['id']}", headers=headers).json()["data"]
    assert detail["status"] == "confirmed"
    assert detail["model_essay_annotations"] is not None
    assert len(detail["model_essay_annotations"]) == 3


def test_draft_edit_expires_annotations_with_essay(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    outline = _chat_propose(client, headers, essay["id"])
    assert outline["model_essay_annotations"] is not None

    patched = client.patch(
        f"/api/v1/outlines/{outline['id']}",
        json={"thesis_statement": "Public transport should stay paid."},
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    detail = client.get(f"/api/v1/outlines/{outline['id']}", headers=headers).json()["data"]
    assert detail["model_essay"] is None
    assert detail["model_essay_annotations"] is None


def test_confirmation_regenerates_annotations_via_v4(client, db):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    outline = _chat_propose(client, headers, essay["id"])
    # Expire the essay, then confirm → ensure_model_essay regenerates (v4).
    assert (
        client.patch(
            f"/api/v1/outlines/{outline['id']}",
            json={"thesis_statement": "Free public transport reduces congestion."},
            headers=headers,
        ).status_code
        == 200
    )

    confirmed = client.post(f"/api/v1/outlines/{outline['id']}/confirm", headers=headers)
    assert confirmed.status_code == 200, confirmed.text
    detail = confirmed.json()["data"]
    assert detail["model_essay_zh"]
    assert detail["model_essay_annotations"] is not None
    assert len(detail["model_essay_annotations"]) == 3

    logs = list(
        db.execute(
            select(AiUsageLog).where(AiUsageLog.feature == "model_essay_generate")
        ).scalars()
    )
    assert logs and logs[0].prompt_version == "v4"


def test_misaligned_model_output_degrades_to_none(client, monkeypatch):
    headers = auth_headers(client)
    essay = create_essay(client, headers)

    def fake_call_llm(*, system, user, response_model):
        assert response_model is PlannerChatResult
        result = PlannerChatResult.model_validate(
            {
                "reply": "拟好了大纲。",
                "action": "propose",
                "outline": {
                    "thesis_statement": "Free public transport is good.",
                    "sections": [
                        {
                            "title": "开头",
                            "paragraphs": [
                                {"title": "引入", "sentence_ideas": ["背景", "立场"]}
                            ],
                        }
                    ],
                },
                "model_essay": "One sentence. Two sentence. Three sentence.",
                "model_essay_zh": "第一句。第二句。第三句。",
                # Only 2 annotations for 3 sentences → must be discarded.
                "sentence_annotations": [
                    _annotation(["One sentence"]).model_dump(),
                    _annotation(["Two sentence"]).model_dump(),
                ],
            }
        )
        return result, LlmUsage(
            provider="mock",
            model_name="mock",
            input_tokens=1,
            output_tokens=1,
            latency_ms=1,
            estimated_cost=0.0,
        )

    monkeypatch.setattr(llm, "call_llm", fake_call_llm)
    outline = _chat_propose(client, headers, essay["id"])
    assert outline["model_essay"] is not None
    assert outline["model_essay_annotations"] is None