"""ADR-026: duplication-free acceptance range resolution.

LLM suggestions sometimes rewrite the whole sentence or include leading
context while the issue anchors a fragment; acceptance must widen the range
instead of duplicating the words before the anchor.
"""

import pytest
from essay_helpers import auth_headers
from grammar_helpers import first_issue, setup_essay_with_text
from sqlalchemy import select

from app.core.exceptions import ApiError
from app.infrastructure.language_tool import client as language_tool
from app.modules.grammar.service import _resolve_replacement_range

TEXT = "He go to school yesterday."


def test_fragment_suggestion_keeps_anchor_range():
    assert _resolve_replacement_range(TEXT, 3, 5, "went") == (3, 5)


def test_whole_sentence_suggestion_widens_to_sentence():
    assert _resolve_replacement_range(TEXT, 3, 5, "He went to school yesterday.") == (0, len(TEXT))


def test_leading_context_overlap_widens_start():
    # Suggestion repeats the subject: replace from sentence start, not anchor.
    assert _resolve_replacement_range(TEXT, 3, 5, "He goes") == (0, 5)


def test_trailing_context_overlap_widens_end():
    assert _resolve_replacement_range(TEXT, 3, 5, "go to school yesterday.") == (3, len(TEXT))


def test_noop_suggestion_rejected():
    with pytest.raises(ApiError) as exc:
        _resolve_replacement_range(TEXT, 3, 5, "go")
    assert exc.value.status_code == 422


@pytest.mark.skipif(
    not language_tool.is_available(),
    reason="LanguageTool is not reachable",
)
def test_accept_whole_sentence_suggestion_has_no_duplication(client, db):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=TEXT)
    issue = first_issue(client, headers, essay["id"], session["id"], TEXT)

    # Force a whole-sentence suggestion onto the detected issue.
    from app.modules.grammar.models import WritingIssue

    row = db.execute(select(WritingIssue).where(WritingIssue.id == issue["id"])).scalar_one()
    for suggestion in row.suggestions:
        suggestion.suggested_text = "He went to school yesterday."
    db.commit()

    response = client.post(
        f"/api/v1/essays/{essay['id']}/issues/{issue['id']}/accept",
        json={"base_revision": 2, "client_revision": 3},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["plain_text"] == "He went to school yesterday."
    assert data["plain_text"].count("He") == 1
    assert data["word_count"] == 5


@pytest.mark.skipif(
    not language_tool.is_available(),
    reason="LanguageTool is not reachable",
)
def test_accept_leading_overlap_suggestion_has_no_duplication(client, db):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=TEXT)
    issue = first_issue(client, headers, essay["id"], session["id"], TEXT)

    from app.modules.grammar.models import WritingIssue

    row = db.execute(select(WritingIssue).where(WritingIssue.id == issue["id"])).scalar_one()
    for suggestion in row.suggestions:
        suggestion.suggested_text = "He goes"
    db.commit()

    response = client.post(
        f"/api/v1/essays/{essay['id']}/issues/{issue['id']}/accept",
        json={"base_revision": 2, "client_revision": 3},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["plain_text"] == "He goes to school yesterday."