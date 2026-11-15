"""Self-correction validation integration tests (atomic, rule-first)."""

import pytest
from essay_helpers import auth_headers, tiptap_doc
from grammar_helpers import all_issues, first_issue, setup_essay_with_text
from sqlalchemy import select

from app.infrastructure.language_tool import client as language_tool
from app.modules.essays.models import EssayEditEvent

pytestmark = pytest.mark.skipif(
    not language_tool.is_available(),
    reason="LanguageTool is not reachable",
)

TEXT = "He go to school."


def _validate(
    client,
    headers,
    essay_id,
    issue_id,
    new_text,
    *,
    base_revision=2,
    modified_start=3,
    modified_end=5,
):
    return client.post(
        f"/api/v1/essays/{essay_id}/issues/validate",
        json={
            "issue_id": issue_id,
            "base_revision": base_revision,
            "client_revision": 2,
            "content_json": tiptap_doc(new_text),
            "plain_text": new_text,
            "word_count": len(new_text.split()),
            "modified_range": {
                "start": modified_start,
                "end": modified_end,
                "offset_unit": "unicode_codepoint",
            },
        },
        headers=headers,
    )


def test_correct_fix_resolves_issue_atomically(client, db):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=TEXT)
    issue = first_issue(client, headers, essay["id"], session["id"], TEXT)

    response = _validate(client, headers, essay["id"], issue["id"], "He goes to school.")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["validation_status"] == "correct"
    assert data["is_resolved"] is True
    assert data["server_revision"] == 3

    working = client.get(f"/api/v1/essays/{essay['id']}/working-document", headers=headers).json()[
        "data"
    ]
    assert working["plain_text"] == "He goes to school."
    assert working["server_revision"] == 3

    detail = client.get(
        f"/api/v1/essays/{essay['id']}/issues/{issue['id']}", headers=headers
    ).json()["data"]
    assert detail["status"] == "resolved"

    events = list(db.execute(select(EssayEditEvent)).scalars())
    assert len(events) == 1
    assert events[0].event_type == "manual_revision"
    assert str(events[0].issue_id) == issue["id"]
    assert events[0].from_server_revision == 2
    assert events[0].to_server_revision == 3


def test_alternative_valid_fix_accepted_not_only_reference(client):
    """'went' is the first suggestion, but a different valid fix must pass."""
    headers = auth_headers(client)
    text = "He go to school yesterday."
    essay, session = setup_essay_with_text(client, headers, text=text)
    issue = first_issue(client, headers, essay["id"], session["id"], text)

    response = _validate(
        client,
        headers,
        essay["id"],
        issue["id"],
        "He went to school yesterday.",
        modified_end=5,
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["validation_status"] == "correct"


def test_incorrect_fix_keeps_issue_and_reanchors(client):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=TEXT)
    issue = first_issue(client, headers, essay["id"], session["id"], TEXT)

    # Edit elsewhere; the agreement error remains.
    response = _validate(
        client,
        headers,
        essay["id"],
        issue["id"],
        "He go to school today.",
        modified_start=14,
        modified_end=16,
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["validation_status"] == "incorrect"
    assert data["is_resolved"] is False

    detail = client.get(
        f"/api/v1/essays/{essay['id']}/issues/{issue['id']}", headers=headers
    ).json()["data"]
    assert detail["status"] == "detected"
    assert detail["source_server_revision"] == 3
    assert detail["anchor_text"] == "go"


def test_stale_base_revision_no_partial_write(client, db):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=TEXT)
    issue = first_issue(client, headers, essay["id"], session["id"], TEXT)

    response = _validate(
        client, headers, essay["id"], issue["id"], "He goes to school.", base_revision=99
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "WORKING_DOCUMENT_CONFLICT"

    working = client.get(f"/api/v1/essays/{essay['id']}/working-document", headers=headers).json()[
        "data"
    ]
    assert working["server_revision"] == 2
    assert working["plain_text"] == TEXT
    assert db.execute(select(EssayEditEvent)).scalars().first() is None


def test_validate_foreign_issue_not_found(client):
    owner = auth_headers(client, "val-owner@example.com")
    intruder = auth_headers(client, "val-intruder@example.com")
    essay, session = setup_essay_with_text(client, owner, text=TEXT)
    issue = first_issue(client, owner, essay["id"], session["id"], TEXT)

    response = _validate(client, intruder, essay["id"], issue["id"], "He goes to school.")
    assert response.status_code == 404


def test_other_issues_survive_validation_of_one(client):
    """ADR-027: fixing one issue keeps the others detected, re-anchored to the
    new revision with shifted offsets (the edit lengthened the text by 2)."""
    headers = auth_headers(client)
    text = "He go to school. He run fast."
    essay, session = setup_essay_with_text(client, headers, text=text)
    issues = all_issues(client, headers, essay["id"], session["id"], text)
    rule_issues = [i for i in issues if i["source"] == "rule_engine"]
    assert len(rule_issues) >= 2
    first = rule_issues[0]
    other = rule_issues[1]

    response = _validate(
        client, headers, essay["id"], first["id"], "He goes to school. He run fast."
    )
    assert response.status_code == 200
    assert response.json()["data"]["validation_status"] == "correct"

    detail = client.get(
        f"/api/v1/essays/{essay['id']}/issues/{other['id']}", headers=headers
    ).json()["data"]
    assert detail["status"] == "detected"
    assert detail["source_server_revision"] == 3
    assert detail["anchor_text"] == other["anchor_text"]
    assert detail["start_offset"] == other["start_offset"] + 2
    assert detail["end_offset"] == other["end_offset"] + 2


def test_validation_stales_only_issues_whose_anchor_disappeared(client):
    headers = auth_headers(client)
    text = "He go to school. He run fast."
    essay, session = setup_essay_with_text(client, headers, text=text)
    issues = all_issues(client, headers, essay["id"], session["id"], text)
    rule_issues = [i for i in issues if i["source"] == "rule_engine"]
    assert len(rule_issues) >= 2
    first = rule_issues[0]
    other = rule_issues[1]

    # The second sentence's anchor ("run") is rewritten by the user.
    response = _validate(
        client, headers, essay["id"], first["id"], "He goes to school. He walks fast."
    )
    assert response.status_code == 200

    detail = client.get(
        f"/api/v1/essays/{essay['id']}/issues/{other['id']}", headers=headers
    ).json()["data"]
    assert detail["status"] == "stale"
