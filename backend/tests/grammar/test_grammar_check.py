"""Grammar check integration tests: real LanguageTool + real PostgreSQL.

Skipped when LanguageTool is not reachable (start it with
`docker compose up -d languagetool`).
"""

import pytest
from essay_helpers import auth_headers
from grammar_helpers import check_text, first_issue, setup_essay_with_text
from sqlalchemy import select

from app.infrastructure.language_tool import client as language_tool
from app.modules.analytics.models import AiUsageLog

pytestmark = pytest.mark.skipif(
    not language_tool.is_available(),
    reason="LanguageTool is not reachable; start it with 'docker compose up -d languagetool'",
)

TEXT = "He go to school yesterday."


def test_check_detects_agreement_error_with_masked_suggestions(client):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers)

    response = check_text(client, headers, essay["id"], session["id"], TEXT)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["server_revision"] == 2
    assert data["check_status"] in ("completed", "partial")
    assert len(data["issues"]) >= 1
    issue = data["issues"][0]
    assert issue["category"] == "grammar"
    assert issue["anchor_text"] == "go"
    assert issue["start_offset"] == 3
    assert issue["end_offset"] == 5
    assert issue["offset_unit"] == "unicode_codepoint"
    assert issue["source_server_revision"] == 2
    assert issue["status"] == "detected"
    assert issue["short_explanation"]
    for suggestion in issue["suggestions"]:
        assert suggestion["display_text"] == "••••"
        assert suggestion["answer_revealed"] is False
        assert "suggested_text" not in suggestion
    # No unrevealed answer anywhere in the raw payload.
    assert "went" not in response.text
    assert "goes" not in response.text


def test_deterministic_rules_instant_plus_one_sentence_scan(client, db):
    """ADR-025: deterministic rule hits never wait for the LLM, and every
    completed sentence gets exactly one whole-sentence scan (no fragment
    deep-check when nothing is uncertain)."""
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers)

    response = check_text(client, headers, essay["id"], session["id"], TEXT)
    assert response.status_code == 200
    assert response.json()["data"]["issues"]  # deterministic hit still present
    logs = list(db.execute(select(AiUsageLog)).scalars())
    assert [log.feature for log in logs] == ["grammar_sentence_check"]


def test_clean_text_returns_no_issues(client):
    headers = auth_headers(client)
    text = "She went to school yesterday."
    essay, session = setup_essay_with_text(client, headers, text=text)

    response = check_text(client, headers, essay["id"], session["id"], text)
    assert response.status_code == 200
    assert response.json()["data"]["issues"] == []


def test_sentence_scan_finds_errors_rules_miss(client, monkeypatch):
    """ADR-025: the whole-sentence LLM scan surfaces Chinglish that LT misses;
    model offsets are validated and converted to absolute document offsets."""
    from app.ai import llm
    from app.ai.providers.base import LlmUsage
    from app.ai.schemas import SentenceCheckResult

    text = "I very like this book."
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=text)

    def fake_call_llm(*, system, user, response_model):
        assert response_model is SentenceCheckResult
        return (
            SentenceCheckResult.model_validate(
                {
                    "issues": [
                        {
                            "category": "grammar",
                            "sub_category": "word_order",
                            "severity": "high",
                            "short_explanation": "语序错误：very 不能直接修饰动词 like。",
                            "suggestions": ["really like", "like ... very much"],
                            "confidence": 0.9,
                            "start_offset": 2,
                            "end_offset": 11,
                            "anchor_text": "very like",
                        },
                        {
                            "category": "grammar",
                            "severity": "low",
                            "short_explanation": "越界 span 必须被丢弃。",
                            "suggestions": ["x"],
                            "confidence": 0.9,
                            "start_offset": 0,
                            "end_offset": 999,
                            "anchor_text": "I very like this book.",
                        },
                    ]
                }
            ),
            LlmUsage(
                provider="mock",
                model_name="mock",
                input_tokens=1,
                output_tokens=1,
                latency_ms=1,
                estimated_cost=0.0,
            ),
        )

    monkeypatch.setattr(llm, "call_llm", fake_call_llm)
    response = check_text(client, headers, essay["id"], session["id"], text)
    assert response.status_code == 200, response.text
    issues = response.json()["data"]["issues"]
    assert len(issues) == 1  # invalid span dropped
    issue = issues[0]
    assert issue["source"] == "llm"
    assert issue["start_offset"] == 2
    assert issue["end_offset"] == 11
    assert issue["anchor_text"] == "very like"
    for suggestion in issue["suggestions"]:
        assert suggestion["display_text"] == "••••"
    assert "really like" not in response.text


def test_independent_mode_is_rejected_backend_side(client):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, mode="independent")

    response = check_text(client, headers, essay["id"], session["id"], TEXT)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "RESOURCE_ACCESS_DENIED"


def test_stale_revision_rejected(client):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers)

    response = check_text(client, headers, essay["id"], session["id"], TEXT, revision=1)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STALE_AI_RESULT"


def test_text_range_mismatch_rejected(client):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers)

    response = check_text(client, headers, essay["id"], session["id"], "Completely different text.")
    assert response.status_code == 422


def test_foreign_session_rejected(client):
    owner = auth_headers(client, "gram-owner@example.com")
    intruder = auth_headers(client, "gram-intruder@example.com")
    essay, session = setup_essay_with_text(client, owner)

    response = check_text(client, intruder, essay["id"], session["id"], TEXT)
    assert response.status_code == 404


def test_recheck_same_revision_reuses_issues(client):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers)

    first = check_text(client, headers, essay["id"], session["id"], TEXT).json()["data"]
    second = check_text(client, headers, essay["id"], session["id"], TEXT).json()["data"]
    assert [i["id"] for i in first["issues"]] == [i["id"] for i in second["issues"]]

    listing = client.get(f"/api/v1/essays/{essay['id']}/issues?revision=2", headers=headers).json()[
        "data"
    ]["items"]
    assert len(listing) == len(first["issues"])


def test_chinese_punctuation_detected(client):
    headers = auth_headers(client)
    text = "Hello，world."
    essay, session = setup_essay_with_text(client, headers, text=text)

    response = check_text(client, headers, essay["id"], session["id"], text)
    assert response.status_code == 200
    issues = response.json()["data"]["issues"]
    assert any(i["rule_id"] == "AWC_CHINESE_PUNCTUATION" for i in issues)


def test_emoji_offsets_are_codepoints(client):
    headers = auth_headers(client)
    text = "🎉 He go to school."
    essay, session = setup_essay_with_text(client, headers, text=text)

    response = check_text(client, headers, essay["id"], session["id"], text)
    assert response.status_code == 200
    issues = response.json()["data"]["issues"]
    go_issue = next(i for i in issues if i["anchor_text"] == "go")
    assert go_issue["start_offset"] == 5
    assert go_issue["end_offset"] == 7


def test_reveal_returns_full_suggestions_only_on_request(client):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers)
    issue = first_issue(client, headers, essay["id"], session["id"], TEXT)

    detail = client.get(
        f"/api/v1/essays/{essay['id']}/issues/{issue['id']}", headers=headers
    ).json()["data"]
    assert all("suggested_text" not in s for s in detail["suggestions"])

    revealed = client.post(
        f"/api/v1/essays/{essay['id']}/issues/{issue['id']}/reveal", headers=headers
    )
    assert revealed.status_code == 200
    suggestions = revealed.json()["data"]["suggestions"]
    assert len(suggestions) >= 1
    assert any(s["suggested_text"] in ("went", "goes") for s in suggestions)
    assert suggestions[0]["is_recommended"] is True


def test_ignore_issue(client):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers)
    issue = first_issue(client, headers, essay["id"], session["id"], TEXT)

    ignored = client.patch(
        f"/api/v1/essays/{essay['id']}/issues/{issue['id']}",
        json={"status": "ignored"},
        headers=headers,
    )
    assert ignored.status_code == 200
    assert ignored.json()["data"]["status"] == "ignored"

    again = client.patch(
        f"/api/v1/essays/{essay['id']}/issues/{issue['id']}",
        json={"status": "ignored"},
        headers=headers,
    )
    assert again.status_code == 409


def test_issue_isolation(client):
    owner = auth_headers(client, "iso-owner@example.com")
    intruder = auth_headers(client, "iso-intruder@example.com")
    essay, session = setup_essay_with_text(client, owner)
    issue = first_issue(client, owner, essay["id"], session["id"], TEXT)

    assert client.get(f"/api/v1/essays/{essay['id']}/issues", headers=intruder).status_code == 404
    assert (
        client.get(
            f"/api/v1/essays/{essay['id']}/issues/{issue['id']}", headers=intruder
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/essays/{essay['id']}/issues/{issue['id']}/reveal", headers=intruder
        ).status_code
        == 404
    )
