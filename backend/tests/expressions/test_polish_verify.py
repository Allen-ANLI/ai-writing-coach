"""ADR-036 polish consistency loop: narrowed v3 criterion + substitution
re-check by the SAME judge before anything is offered or persisted.

The judge re-checks its own flag (original_unnatural) and judges each option
inserted back into the sentence (option_unnatural). Only candidates with
original_unnatural=true AND option_unnatural=false survive; verify failure
fails closed. The mock judge treats 'very like' as the unnatural pattern.
"""

from essay_helpers import auth_headers
from grammar_helpers import setup_essay_with_text
from sqlalchemy import select

from app.ai import llm
from app.ai.providers.base import LlmUsage
from app.ai.schemas import (
    PolishFragment,
    PolishOption,
    PolishSentenceResult,
    PolishVerifyResult,
)
from app.core.exceptions import ApiError
from app.modules.analytics.models import AiUsageLog
from app.modules.expressions.models import ExpressionSuggestion

UNNATURAL = "I very like this book."
NATURAL = "She went to school yesterday."


def _polish(client, headers, essay_id, session_id, sentence, **extra):
    return client.post(
        f"/api/v1/essays/{essay_id}/expressions/polish-sentence",
        json={
            "session_id": session_id,
            "server_revision": 2,
            "client_revision": 1,
            "sentence": sentence,
            "sentence_range": {
                "start": 0,
                "end": len(sentence),
                "offset_unit": "unicode_codepoint",
            },
            **extra,
        },
        headers=headers,
    )


def _usage() -> LlmUsage:
    return LlmUsage(
        provider="mock",
        model_name="mock",
        input_tokens=1,
        output_tokens=1,
        latency_ms=1,
        estimated_cost=0.0,
    )


def _option(text: str) -> PolishOption:
    return PolishOption(text=text, meaning="含义", usage="用法", formality="neutral")


def _fragment(sentence: str, anchor: str, options: list[str]) -> PolishFragment:
    start = sentence.index(anchor)
    return PolishFragment(
        anchor_text=anchor,
        start_offset=start,
        end_offset=start + len(anchor),
        note="测试片段",
        options=[_option(t) for t in options],
    )


def _patch_polish(monkeypatch, sentence: str, fragment: PolishFragment | None):
    """Serve a crafted polish result; the verify call runs the real mock judge."""
    real_call_llm = llm.call_llm

    def fake(*, system, user, response_model):
        if response_model is PolishSentenceResult:
            result = PolishSentenceResult(fragments=[fragment] if fragment else [])
            return result, _usage()
        return real_call_llm(system=system, user=user, response_model=response_model)

    monkeypatch.setattr(llm, "call_llm", fake)


def test_verify_filters_option_that_leaves_the_problem(client, db, monkeypatch):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=UNNATURAL)
    _patch_polish(
        monkeypatch,
        UNNATURAL,
        _fragment(UNNATURAL, "very like", ["really like", "very like", "love"]),
    )

    response = _polish(client, headers, essay["id"], session["id"], UNNATURAL)
    assert response.status_code == 200, response.text
    fragments = response.json()["data"]["fragments"]
    assert len(fragments) == 1
    texts = {item["english_text"] for item in fragments[0]["items"]}
    # The no-op option leaves 'very like' in the substituted sentence → the
    # same judge flags it → it must never be offered or persisted.
    assert texts == {"really like", "love"}
    items = list(db.execute(select(ExpressionSuggestion)).scalars())
    assert len(items) == 1
    assert len(items[0].items) == 2


def test_verify_rejects_false_positive_flag(client, db, monkeypatch):
    """The judge re-checks its own flag: a natural sentence wrongly flagged
    by the detector yields no fragments (model-essay false-positive guard)."""
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=NATURAL)
    _patch_polish(
        monkeypatch,
        NATURAL,
        _fragment(NATURAL, "went to", ["walked to", "headed to", "went towards"]),
    )

    response = _polish(client, headers, essay["id"], session["id"], NATURAL)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["fragments"] == []
    assert db.execute(select(ExpressionSuggestion)).scalars().first() is None


def test_verify_all_options_fail_drops_fragment(client, monkeypatch):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=UNNATURAL)
    _patch_polish(
        monkeypatch,
        UNNATURAL,
        _fragment(UNNATURAL, "very like", ["very like", "very like much", "I very like"]),
    )

    response = _polish(client, headers, essay["id"], session["id"], UNNATURAL)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["fragments"] == []


def test_verify_failure_fails_closed(client, db, monkeypatch):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=UNNATURAL)
    real_call_llm = llm.call_llm

    def fake(*, system, user, response_model):
        if response_model is PolishSentenceResult:
            result = PolishSentenceResult(
                fragments=[_fragment(UNNATURAL, "very like", ["really like", "am fond of", "love"])]
            )
            return result, _usage()
        if response_model is PolishVerifyResult:
            raise ApiError(502, "LLM_PROVIDER_ERROR", "The AI service failed.")
        return real_call_llm(system=system, user=user, response_model=response_model)

    monkeypatch.setattr(llm, "call_llm", fake)

    response = _polish(client, headers, essay["id"], session["id"], UNNATURAL)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["fragments"] == []
    assert db.execute(select(ExpressionSuggestion)).scalars().first() is None
    logs = list(db.execute(select(AiUsageLog)).scalars())
    by_feature = {log.feature: log.status for log in logs}
    assert by_feature["expression_polish"] == "success"
    assert by_feature["polish_verify"] == "error"


def test_natural_sentence_skips_verify_call(client, monkeypatch):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=NATURAL)
    real_call_llm = llm.call_llm
    calls = []

    def counting(*, system, user, response_model):
        calls.append(response_model)
        return real_call_llm(system=system, user=user, response_model=response_model)

    monkeypatch.setattr(llm, "call_llm", counting)

    response = _polish(client, headers, essay["id"], session["id"], NATURAL)
    assert response.status_code == 200
    assert response.json()["data"]["fragments"] == []
    assert calls == [PolishSentenceResult]  # no candidates → no verify spend


def test_successful_scan_logs_both_calls(client, db):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=UNNATURAL)

    response = _polish(client, headers, essay["id"], session["id"], UNNATURAL)
    assert response.status_code == 200, response.text
    assert len(response.json()["data"]["fragments"]) == 1
    logs = list(db.execute(select(AiUsageLog)).scalars())
    by_feature = {log.feature: log for log in logs}
    assert by_feature["expression_polish"].status == "success"
    assert by_feature["expression_polish"].prompt_version == "v3"
    assert by_feature["polish_verify"].status == "success"
    assert by_feature["polish_verify"].prompt_version == "v1"


def test_pagination_options_are_also_verified(client, monkeypatch):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=UNNATURAL)
    _patch_polish(
        monkeypatch,
        UNNATURAL,
        _fragment(UNNATURAL, "very like", ["really like", "very like", "love"]),
    )

    response = _polish(
        client,
        headers,
        essay["id"],
        session["id"],
        UNNATURAL,
        fragment_anchor="very like",
        exclude=["really like"],
    )
    assert response.status_code == 200, response.text
    fragments = response.json()["data"]["fragments"]
    assert len(fragments) == 1
    texts = {item["english_text"] for item in fragments[0]["items"]}
    assert texts == {"really like", "love"}


def test_mock_judge_parses_candidate_indices():
    from app.ai.providers.mock import MockProvider

    user = (
        "Original sentence: I very like this book.\n"
        "Candidates:\n"
        "[1] anchor: very like | option: really like\n"
        "    substituted: I really like this book.\n"
        "[2] anchor: very like | option: very like\n"
        "    substituted: I very like this book.\n"
        "Return JSON: results (candidate_index, original_unnatural, option_unnatural)."
    )
    result = MockProvider().complete_json(
        system="judge", user=user, response_model=PolishVerifyResult
    )
    parsed = PolishVerifyResult.model_validate(result.content_json)
    verdicts = [
        (r.candidate_index, r.original_unnatural, r.option_unnatural) for r in parsed.results
    ]
    assert verdicts == [(1, True, False), (2, True, True)]