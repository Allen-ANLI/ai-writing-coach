"""ADR-034 live grammar check: Word-like instant rule-only, ephemeral.

Live mode skips the saved-revision / text_range-vs-doc gate, runs only the
deterministic rule engine (no LLM, no billing), persists nothing, and exposes
suggestions inline (revealed) so they display instantly. Acceptance happens
after save via the full check. Skipped when LanguageTool is unreachable.
"""

import pytest
from essay_helpers import auth_headers
from grammar_helpers import setup_essay_with_text
from sqlalchemy import select

from app.infrastructure.language_tool import client as language_tool
from app.modules.analytics.models import AiUsageLog
from app.modules.grammar.models import WritingIssue

pytestmark = pytest.mark.skipif(
    not language_tool.is_available(),
    reason="LanguageTool is not reachable; start it with 'docker compose up -d languagetool'",
)

TEXT = "He go to school yesterday."


def live_check(
    client, headers, essay_id, session_id, text, *, revision=2, start=0, sentence_complete=True
):
    return client.post(
        f"/api/v1/essays/{essay_id}/grammar-check",
        json={
            "session_id": session_id,
            "server_revision": revision,
            "client_revision": 1,
            "text": text,
            "text_range": {
                "start": start,
                "end": start + len(text),
                "offset_unit": "unicode_codepoint",
            },
            "context": {"paragraph_text": text},
            "live": True,
            "sentence_complete": sentence_complete,
        },
        headers=headers,
    )


def test_live_returns_revealed_deterministic_issues(client, db):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers)

    response = live_check(client, headers, essay["id"], session["id"], TEXT)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["check_status"] == "live"
    assert data["issues"]
    issue = data["issues"][0]
    assert issue["live"] is True
    assert issue["category"] == "grammar"
    assert issue["anchor_text"] == "go"
    assert issue["start_offset"] == 3
    assert issue["end_offset"] == 5
    assert issue["short_explanation"]
    for suggestion in issue["suggestions"]:
        assert suggestion["answer_revealed"] is True
        assert suggestion["display_text"] != "••••"
    # Ephemeral: nothing persisted and no LLM usage recorded.
    assert db.execute(select(WritingIssue)).scalars().first() is None
    assert db.execute(select(AiUsageLog)).scalars().first() is None


def test_live_never_calls_the_llm(client, monkeypatch):
    from app.ai import llm

    def boom(**kwargs):
        raise AssertionError("live check must not call the LLM")

    monkeypatch.setattr(llm, "call_llm", boom)
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers)

    response = live_check(client, headers, essay["id"], session["id"], TEXT)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["issues"]


def test_live_ignores_saved_revision_and_text_gate(client):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers)

    # Stale revision AND text differing from the saved doc: still instant 200.
    response = live_check(
        client, headers, essay["id"], session["id"], "He go to school today.", revision=99
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["check_status"] == "live"


def test_live_offsets_are_absolute(client):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers)

    response = live_check(client, headers, essay["id"], session["id"], TEXT, start=10)
    assert response.status_code == 200, response.text
    issue = response.json()["data"]["issues"][0]
    assert issue["start_offset"] == 13
    assert issue["end_offset"] == 15


def test_live_ids_are_stable_across_rechecks(client):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers)

    first = live_check(client, headers, essay["id"], session["id"], TEXT).json()["data"]
    second = live_check(client, headers, essay["id"], session["id"], TEXT).json()["data"]
    assert [i["id"] for i in first["issues"]] == [i["id"] for i in second["issues"]]


def test_live_independent_mode_rejected(client):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, mode="independent")

    response = live_check(client, headers, essay["id"], session["id"], TEXT)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "RESOURCE_ACCESS_DENIED"


def test_live_foreign_session_rejected(client):
    owner = auth_headers(client, "live-owner@example.com")
    intruder = auth_headers(client, "live-intruder@example.com")
    essay, session = setup_essay_with_text(client, owner)

    response = live_check(client, intruder, essay["id"], session["id"], TEXT)
    assert response.status_code == 404


# --- ADR-035: incomplete sentences are never judged prematurely -------------


def test_live_incomplete_sentence_suppresses_grammar(client):
    """Word + space mid-sentence must not produce a grammar verdict: the
    writer is still composing (e.g. "He go…" on the way to "He goes…")."""
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers)

    response = live_check(
        client, headers, essay["id"], session["id"], "He go to school", sentence_complete=False
    )
    assert response.status_code == 200, response.text
    issues = response.json()["data"]["issues"]
    assert [i for i in issues if i["category"] != "spelling"] == []


def test_live_complete_sentence_shows_grammar(client):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers)

    response = live_check(
        client, headers, essay["id"], session["id"], "He go to school", sentence_complete=True
    )
    assert response.status_code == 200, response.text
    issues = response.json()["data"]["issues"]
    assert any(i["anchor_text"] == "go" and i["category"] == "grammar" for i in issues)


def test_live_sentence_complete_defaults_to_false(client):
    """Omitting the flag (older clients) must not judge incomplete input."""
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers)

    response = client.post(
        f"/api/v1/essays/{essay['id']}/grammar-check",
        json={
            "session_id": session["id"],
            "server_revision": 2,
            "client_revision": 1,
            "text": "He go to school",
            "text_range": {"start": 0, "end": 15, "offset_unit": "unicode_codepoint"},
            "live": True,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    issues = response.json()["data"]["issues"]
    assert [i for i in issues if i["category"] != "spelling"] == []


def test_live_spelling_finalized_word_shows_mid_sentence(client):
    """A misspelled word followed by a space is finalized — Word-like instant
    spelling feedback even though the sentence is incomplete."""
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers)

    response = live_check(
        client, headers, essay["id"], session["id"], "I recieve the letter", sentence_complete=False
    )
    assert response.status_code == 200, response.text
    issues = response.json()["data"]["issues"]
    assert any(i["category"] == "spelling" and i["anchor_text"] == "recieve" for i in issues)


def test_live_spelling_unfinalized_word_suppressed(client):
    """Cursor right after the word (no space yet): the writer may still be
    typing it, so no spelling verdict."""
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers)

    response = live_check(
        client, headers, essay["id"], session["id"], "I recieve", sentence_complete=False
    )
    assert response.status_code == 200, response.text
    issues = response.json()["data"]["issues"]
    assert all(i["anchor_text"] != "recieve" for i in issues)


def test_live_spelling_finalized_by_punctuation(client):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers)

    response = live_check(
        client, headers, essay["id"], session["id"], "I recieve.", sentence_complete=False
    )
    assert response.status_code == 200, response.text
    issues = response.json()["data"]["issues"]
    assert any(i["category"] == "spelling" and i["anchor_text"] == "recieve" for i in issues)


def test_live_spelling_last_word_of_complete_span_shows(client):
    """Paragraph break: the span ends before the separator, so the last word
    has no following character in the submitted text — a complete span still
    finalizes it."""
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers)

    response = live_check(
        client, headers, essay["id"], session["id"], "I recieve", sentence_complete=True
    )
    assert response.status_code == 200, response.text
    issues = response.json()["data"]["issues"]
    assert any(i["category"] == "spelling" and i["anchor_text"] == "recieve" for i in issues)