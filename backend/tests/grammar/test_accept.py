"""Suggestion acceptance integration tests (user UX decision 2026-11-15 §2.5).

Atomic server-side application of stored corrections: revision increment,
issue resolution, suggestion acceptance, Edit Event, conflict safety.
"""

import pytest
from essay_helpers import auth_headers
from grammar_helpers import first_issue, setup_essay_with_text
from sqlalchemy import select

from app.infrastructure.language_tool import client as language_tool
from app.modules.essays.models import EssayEditEvent

pytestmark = pytest.mark.skipif(
    not language_tool.is_available(),
    reason="LanguageTool is not reachable",
)

TEXT = "He go to school yesterday."


def _accept(client, headers, essay_id, issue_id, *, base_revision=2, suggestion_id=None):
    payload = {"base_revision": base_revision, "client_revision": 3}
    if suggestion_id is not None:
        payload["suggestion_id"] = suggestion_id
    return client.post(
        f"/api/v1/essays/{essay_id}/issues/{issue_id}/accept",
        json=payload,
        headers=headers,
    )


def test_accept_applies_stored_correction_atomically(client, db):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=TEXT)
    issue = first_issue(client, headers, essay["id"], session["id"], TEXT)

    response = _accept(client, headers, essay["id"], issue["id"])
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["server_revision"] == 3
    assert data["applied_text"] in ("went", "goes")
    assert data["plain_text"] == TEXT.replace("go", data["applied_text"])
    assert data["word_count"] == len(data["plain_text"].split())

    working = client.get(f"/api/v1/essays/{essay['id']}/working-document", headers=headers).json()[
        "data"
    ]
    assert working["server_revision"] == 3
    assert working["plain_text"] == data["plain_text"]

    detail = client.get(
        f"/api/v1/essays/{essay['id']}/issues/{issue['id']}", headers=headers
    ).json()["data"]
    assert detail["status"] == "resolved"

    events = list(db.execute(select(EssayEditEvent)).scalars())
    assert len(events) == 1
    assert events[0].event_type == "accept_suggestion"
    assert events[0].actor_type == "ai_accept"
    assert str(events[0].suggestion_id) == data["suggestion_id"]
    assert events[0].before_text == "go"
    assert events[0].after_text == data["applied_text"]


def test_accept_specific_suggestion(client):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=TEXT)
    issue = first_issue(client, headers, essay["id"], session["id"], TEXT)
    revealed = client.post(
        f"/api/v1/essays/{essay['id']}/issues/{issue['id']}/reveal", headers=headers
    ).json()["data"]["suggestions"]
    chosen = revealed[-1]

    response = _accept(client, headers, essay["id"], issue["id"], suggestion_id=chosen["id"])
    assert response.status_code == 200, response.text
    assert response.json()["data"]["applied_text"] == chosen["suggested_text"]


def test_accept_conflict_no_partial_write(client, db):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=TEXT)
    issue = first_issue(client, headers, essay["id"], session["id"], TEXT)

    response = _accept(client, headers, essay["id"], issue["id"], base_revision=99)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "WORKING_DOCUMENT_CONFLICT"

    working = client.get(f"/api/v1/essays/{essay['id']}/working-document", headers=headers).json()[
        "data"
    ]
    assert working["server_revision"] == 2
    assert working["plain_text"] == TEXT
    assert db.execute(select(EssayEditEvent)).scalars().first() is None


def test_accept_twice_rejected(client):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=TEXT)
    issue = first_issue(client, headers, essay["id"], session["id"], TEXT)

    assert _accept(client, headers, essay["id"], issue["id"]).status_code == 200
    again = _accept(client, headers, essay["id"], issue["id"], base_revision=3)
    assert again.status_code == 409


def test_accept_foreign_issue_not_found(client):
    owner = auth_headers(client, "acc-owner@example.com")
    intruder = auth_headers(client, "acc-intruder@example.com")
    essay, session = setup_essay_with_text(client, owner, text=TEXT)
    issue = first_issue(client, owner, essay["id"], session["id"], TEXT)

    assert _accept(client, intruder, essay["id"], issue["id"]).status_code == 404


def test_accept_preserves_surrounding_structure(client):
    headers = auth_headers(client)
    text = "First paragraph stays. He go to school yesterday. Last part stays."
    essay, session = setup_essay_with_text(client, headers, text=text)
    issue = first_issue(client, headers, essay["id"], session["id"], text)

    response = _accept(client, headers, essay["id"], issue["id"])
    assert response.status_code == 200, response.text
    new_text = response.json()["data"]["plain_text"]
    assert new_text.startswith("First paragraph stays. ")
    assert new_text.endswith(" Last part stays.")
    assert " go " not in new_text
