"""Contextual teaching integration tests (mock LLM provider by default).

Verifies pipeline behavior: caching, context hashing, usage logging,
personalized-note enforcement. Linguistic quality is evaluated separately
with a real provider (evaluation deliverable).
"""

from essay_helpers import auth_headers
from grammar_helpers import first_issue, setup_essay_with_text
from sqlalchemy import select

from app.modules.analytics.models import AiUsageLog
from app.modules.grammar.models import IssueTeaching

TEXT = "He go to school yesterday."


def _teaching(
    client,
    headers,
    essay_id,
    issue_id,
    *,
    revision=2,
    sentence=TEXT,
    paragraph=None,
    user_text=None,
):
    return client.post(
        f"/api/v1/essays/{essay_id}/issues/{issue_id}/teaching",
        json={
            "server_revision": revision,
            "client_revision": 1,
            "current_sentence": sentence,
            "paragraph_context": paragraph,
            "user_current_text": user_text,
        },
        headers=headers,
    )


def test_teaching_generated_logged_and_personalized_note_null(client, db):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers)
    issue = first_issue(client, headers, essay["id"], session["id"], TEXT)

    response = _teaching(client, headers, essay["id"], issue["id"])
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["issue_id"] == issue["id"]
    assert data["source_server_revision"] == 2
    assert data["title"]
    # ADR-026: structured v2 — knowledge point first, then sentence reason.
    assert data["knowledge_point"]["explanation"]
    assert data["knowledge_point"]["pattern"]
    assert len(data["knowledge_point"]["examples"]) >= 2
    assert data["sentence_reason"]
    assert data["recommended_correction"]
    assert data["personalized_note"] is None  # no verified weakness history yet

    logs = [log for log in db.execute(select(AiUsageLog)).scalars() if log.feature == "teaching"]
    assert len(logs) == 1
    assert logs[0].provider == "mock"
    assert logs[0].prompt_version == "v2"
    assert logs[0].status == "success"

    teachings = list(db.execute(select(IssueTeaching)).scalars())
    assert len(teachings) == 1
    assert teachings[0].context_snapshot["current_sentence"] == TEXT


def test_teaching_cached_for_same_context(client, db):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers)
    issue = first_issue(client, headers, essay["id"], session["id"], TEXT)

    first = _teaching(client, headers, essay["id"], issue["id"]).json()["data"]
    second = _teaching(client, headers, essay["id"], issue["id"]).json()["data"]
    assert first["teaching_id"] == second["teaching_id"]
    teaching_logs = [
        log for log in db.execute(select(AiUsageLog)).scalars() if log.feature == "teaching"
    ]
    assert len(teaching_logs) == 1


def test_teaching_context_change_regenerates(client, db):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers)
    issue = first_issue(client, headers, essay["id"], session["id"], TEXT)

    first = _teaching(client, headers, essay["id"], issue["id"]).json()["data"]
    second = _teaching(
        client, headers, essay["id"], issue["id"], sentence="He goed to school yesterday."
    ).json()["data"]
    assert first["teaching_id"] != second["teaching_id"]
    assert len(list(db.execute(select(IssueTeaching)).scalars())) == 2


def test_teaching_stale_revision_rejected(client):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers)
    issue = first_issue(client, headers, essay["id"], session["id"], TEXT)

    response = _teaching(client, headers, essay["id"], issue["id"], revision=99)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STALE_AI_RESULT"


def test_teaching_foreign_issue_not_found(client):
    owner = auth_headers(client, "teach-owner@example.com")
    intruder = auth_headers(client, "teach-intruder@example.com")
    essay, session = setup_essay_with_text(client, owner)
    issue = first_issue(client, owner, essay["id"], session["id"], TEXT)

    response = _teaching(client, intruder, essay["id"], issue["id"])
    assert response.status_code == 404
