"""ADR-035 live-accept: atomic acceptance of ephemeral live findings.

One server call re-derives the deterministic rule hit (rule engine only, no
LLM, no billing), verifies the chosen replacement is among the server-derived
suggestions, find-or-creates the issue row and applies the correction through
the shared atomic acceptance transaction. Replaces the fragile
save→full-check→reveal→accept chain. Skipped when LanguageTool is unreachable.
"""

import pytest
from essay_helpers import auth_headers, save_document
from grammar_helpers import check_text, setup_essay_with_text
from sqlalchemy import select

from app.infrastructure.language_tool import client as language_tool
from app.modules.analytics.models import AiUsageLog
from app.modules.essays.models import EssayEditEvent
from app.modules.grammar.models import WritingIssue

pytestmark = pytest.mark.skipif(
    not language_tool.is_available(),
    reason="LanguageTool is not reachable; start it with 'docker compose up -d languagetool'",
)

SPELLING_TEXT = "I recieve the letter."


def _live_spelling_finding(client, headers, essay_id, session_id, text, *, sentence_complete=True):
    response = client.post(
        f"/api/v1/essays/{essay_id}/grammar-check",
        json={
            "session_id": session_id,
            "server_revision": 2,
            "client_revision": 1,
            "text": text,
            "text_range": {
                "start": 0,
                "end": len(text),
                "offset_unit": "unicode_codepoint",
            },
            "context": {"paragraph_text": text},
            "live": True,
            "sentence_complete": sentence_complete,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    issues = response.json()["data"]["issues"]
    spelling = [i for i in issues if i["category"] == "spelling"]
    assert spelling, response.text
    return spelling[0]


def _live_accept(
    client,
    headers,
    essay_id,
    session_id,
    finding,
    *,
    base_revision=2,
    replacement=None,
    rule_id=None,
):
    return client.post(
        f"/api/v1/essays/{essay_id}/issues/live-accept",
        json={
            "session_id": session_id,
            "base_revision": base_revision,
            "client_revision": 3,
            "rule_id": rule_id if rule_id is not None else finding["rule_id"],
            "start_offset": finding["start_offset"],
            "end_offset": finding["end_offset"],
            "anchor_text": finding["anchor_text"],
            "replacement": (
                replacement
                if replacement is not None
                else finding["suggestions"][0]["display_text"]
            ),
        },
        headers=headers,
    )


def test_live_accept_applies_spelling_correction_atomically(client, db, monkeypatch):
    from app.ai import llm

    def boom(**kwargs):
        raise AssertionError("live-accept must not call the LLM")

    monkeypatch.setattr(llm, "call_llm", boom)
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=SPELLING_TEXT)
    finding = _live_spelling_finding(client, headers, essay["id"], session["id"], SPELLING_TEXT)

    response = _live_accept(client, headers, essay["id"], session["id"], finding)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["server_revision"] == 3
    assert data["applied_text"] == finding["suggestions"][0]["display_text"]
    assert data["plain_text"] == SPELLING_TEXT.replace("recieve", data["applied_text"])
    assert "recieve" not in data["plain_text"]

    working = client.get(
        f"/api/v1/essays/{essay['id']}/working-document", headers=headers
    ).json()["data"]
    assert working["server_revision"] == 3
    assert working["plain_text"] == data["plain_text"]

    issues = list(db.execute(select(WritingIssue)).scalars())
    assert len(issues) == 1
    assert issues[0].status == "resolved"
    assert issues[0].category == "spelling"
    assert issues[0].resolved_by_server_revision == 3

    events = list(db.execute(select(EssayEditEvent)).scalars())
    assert len(events) == 1
    assert events[0].event_type == "accept_suggestion"
    assert events[0].actor_type == "ai_accept"
    assert events[0].before_text == "recieve"
    assert events[0].after_text == data["applied_text"]
    # No LLM call, no billing/usage record.
    assert db.execute(select(AiUsageLog)).scalars().first() is None


def test_live_accept_works_mid_sentence_without_terminator(client):
    """The common spelling case: the sentence is still incomplete, but the
    misspelled word is finalized — acceptance must work without a period."""
    headers = auth_headers(client)
    text = "I recieve the letter"
    essay, session = setup_essay_with_text(client, headers, text=text)
    finding = _live_spelling_finding(
        client, headers, essay["id"], session["id"], text, sentence_complete=False
    )

    response = _live_accept(client, headers, essay["id"], session["id"], finding)
    assert response.status_code == 200, response.text
    assert "recieve" not in response.json()["data"]["plain_text"]


def test_live_accept_conflict_no_partial_write(client, db):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=SPELLING_TEXT)
    finding = _live_spelling_finding(client, headers, essay["id"], session["id"], SPELLING_TEXT)

    response = _live_accept(
        client, headers, essay["id"], session["id"], finding, base_revision=99
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "WORKING_DOCUMENT_CONFLICT"

    working = client.get(
        f"/api/v1/essays/{essay['id']}/working-document", headers=headers
    ).json()["data"]
    assert working["server_revision"] == 2
    assert working["plain_text"] == SPELLING_TEXT
    assert db.execute(select(WritingIssue)).scalars().first() is None
    assert db.execute(select(EssayEditEvent)).scalars().first() is None


def test_live_accept_replacement_outside_server_suggestions_rejected(client, db):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=SPELLING_TEXT)
    finding = _live_spelling_finding(client, headers, essay["id"], session["id"], SPELLING_TEXT)

    response = _live_accept(
        client,
        headers,
        essay["id"],
        session["id"],
        finding,
        replacement="totally-free-client-text",
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    working = client.get(
        f"/api/v1/essays/{essay['id']}/working-document", headers=headers
    ).json()["data"]
    assert working["plain_text"] == SPELLING_TEXT
    assert db.execute(select(WritingIssue)).scalars().first() is None


def test_live_accept_disappeared_anchor_rejected(client):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=SPELLING_TEXT)
    finding = _live_spelling_finding(client, headers, essay["id"], session["id"], SPELLING_TEXT)

    # The user already fixed the word themselves.
    assert (
        save_document(
            client,
            headers,
            essay["id"],
            base_revision=2,
            paragraphs=("I receive the letter.",),
        ).status_code
        == 200
    )

    response = _live_accept(
        client, headers, essay["id"], session["id"], finding, base_revision=3
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STALE_AI_RESULT"


def test_live_accept_unknown_rule_rejected(client):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=SPELLING_TEXT)
    finding = _live_spelling_finding(client, headers, essay["id"], session["id"], SPELLING_TEXT)

    response = _live_accept(
        client, headers, essay["id"], session["id"], finding, rule_id="NO_SUCH_RULE"
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STALE_AI_RESULT"


def test_live_accept_reuses_persisted_issue_no_duplicate(client, db):
    """A full check may already have persisted the same finding; live-accept
    must resolve that row instead of creating a duplicate."""
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=SPELLING_TEXT)
    checked = check_text(client, headers, essay["id"], session["id"], SPELLING_TEXT)
    assert checked.status_code == 200, checked.text
    finding = _live_spelling_finding(client, headers, essay["id"], session["id"], SPELLING_TEXT)

    response = _live_accept(client, headers, essay["id"], session["id"], finding)
    assert response.status_code == 200, response.text

    issues = list(db.execute(select(WritingIssue)).scalars())
    assert len(issues) == 1
    assert issues[0].status == "resolved"
    assert str(issues[0].id) == response.json()["data"]["issue_id"]


def test_live_accept_preserves_other_detected_issues(client, db):
    headers = auth_headers(client)
    text = "I recieve the letter. He go to school."
    essay, session = setup_essay_with_text(client, headers, text=text)
    checked = check_text(client, headers, essay["id"], session["id"], text)
    assert checked.status_code == 200, checked.text
    finding = _live_spelling_finding(client, headers, essay["id"], session["id"], text)

    response = _live_accept(client, headers, essay["id"], session["id"], finding)
    assert response.status_code == 200, response.text

    others = [
        i
        for i in db.execute(select(WritingIssue)).scalars()
        if str(i.id) != response.json()["data"]["issue_id"]
    ]
    assert others
    assert all(i.status == "detected" for i in others)
    assert all(i.source_server_revision == 3 for i in others)


def test_live_accept_foreign_essay_not_found(client):
    owner = auth_headers(client, "la-owner@example.com")
    intruder = auth_headers(client, "la-intruder@example.com")
    essay, session = setup_essay_with_text(client, owner, text=SPELLING_TEXT)
    finding = _live_spelling_finding(client, owner, essay["id"], session["id"], SPELLING_TEXT)

    response = _live_accept(client, intruder, essay["id"], session["id"], finding)
    assert response.status_code == 404


def test_live_accept_independent_mode_rejected(client):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=SPELLING_TEXT, mode="independent")

    response = client.post(
        f"/api/v1/essays/{essay['id']}/issues/live-accept",
        json={
            "session_id": session["id"],
            "base_revision": 2,
            "client_revision": 3,
            "rule_id": "MORFOLOGIK_RULE_EN_US",
            "start_offset": 2,
            "end_offset": 9,
            "anchor_text": "recieve",
            "replacement": "receive",
        },
        headers=headers,
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "RESOURCE_ACCESS_DENIED"