"""Expression assistance integration tests (API Spec §8, mock LLM provider).

Pipeline behavior: mode enforcement, revision guards, persisted candidates,
usage logging, atomic acceptance. Linguistic quality is evaluated separately
against the real provider (scripts/eval_ai.py).
"""

from essay_helpers import auth_headers, save_document, tiptap_doc
from grammar_helpers import start_session
from sqlalchemy import select

from app.modules.analytics.models import AiUsageLog
from app.modules.essays.models import EssayEditEvent

TEXT = "I want to get more experience in this field."


def _setup(client, mode="assisted"):
    headers = auth_headers(client)
    from essay_helpers import create_essay

    essay = create_essay(client, headers)
    assert (
        save_document(client, headers, essay["id"], base_revision=1, paragraphs=(TEXT,)).status_code
        == 200
    )
    session = start_session(client, headers, essay["id"], mode=mode)
    return headers, essay, session


def _polish(client, headers, essay, session, *, revision=2):
    return client.post(
        f"/api/v1/essays/{essay['id']}/expression-suggestions",
        json={
            "session_id": session["id"],
            "server_revision": revision,
            "client_revision": 1,
            "selected_text": "get more experience",
            "sentence": TEXT,
            "paragraph_context": TEXT,
            "max_suggestions": 3,
        },
        headers=headers,
    )


def _translate(client, headers, essay, session, *, revision=2):
    return client.post(
        f"/api/v1/essays/{essay['id']}/translations",
        json={
            "session_id": session["id"],
            "server_revision": revision,
            "client_revision": 1,
            "chinese_text": "提高公众环保意识",
            "sentence_context": "This policy can raise public awareness.",
            "paragraph_context": "This policy can raise public awareness.",
        },
        headers=headers,
    )


def test_polish_returns_persisted_candidates_and_logs_usage(client, db):
    headers, essay, session = _setup(client)
    response = _polish(client, headers, essay, session)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["kind"] == "polish"
    assert data["status"] == "pending"
    assert len(data["items"]) >= 1
    for item in data["items"]:
        assert item["english_text"]
        assert item["previously_learned"] is False
        assert item["source"] == "llm"

    logs = list(db.execute(select(AiUsageLog)).scalars())
    assert len(logs) == 1
    assert logs[0].feature == "expression_polish"
    assert logs[0].provider == "mock"


def test_polish_independent_mode_rejected(client):
    headers, essay, session = _setup(client, mode="independent")
    response = _polish(client, headers, essay, session)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "RESOURCE_ACCESS_DENIED"


def test_polish_stale_revision_rejected(client):
    headers, essay, session = _setup(client)
    response = _polish(client, headers, essay, session, revision=99)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STALE_AI_RESULT"


def test_translation_returns_candidates(client):
    headers, essay, session = _setup(client)
    response = _translate(client, headers, essay, session)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["kind"] == "translation"
    assert 2 <= len(data["items"]) <= 4
    assert all(i["chinese_meaning"] for i in data["items"])


def test_translation_independent_mode_rejected(client):
    headers, essay, session = _setup(client, mode="independent")
    response = _translate(client, headers, essay, session)
    assert response.status_code == 403


def test_translation_uses_prompt_v2(client, db):
    headers, essay, session = _setup(client)
    assert _translate(client, headers, essay, session).status_code == 200
    logs = list(db.execute(select(AiUsageLog)).scalars())
    assert logs[0].feature == "translation"
    assert logs[0].prompt_version == "v2"


def test_translation_exclude_paginates_with_distinct_candidates(client):
    """ADR-027: the assist card's 查看更多 pages via exclude; the next page
    must not repeat any already-shown expression."""
    headers, essay, session = _setup(client)
    first_page = _translate(client, headers, essay, session).json()["data"]
    exclude = [item["english_text"] for item in first_page["items"]]

    response = client.post(
        f"/api/v1/essays/{essay['id']}/translations",
        json={
            "session_id": session["id"],
            "server_revision": 2,
            "client_revision": 1,
            "chinese_text": "提高公众环保意识",
            "sentence_context": "This policy can raise public awareness.",
            "paragraph_context": "This policy can raise public awareness.",
            "exclude": exclude,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    second_page = response.json()["data"]
    assert len(second_page["items"]) >= 2
    assert all(item["english_text"] not in exclude for item in second_page["items"])
    assert any("[mock:alt_expression]" in item["english_text"] for item in second_page["items"])


def _accept(client, headers, essay, suggestion, item, *, base_revision=2, text=None):
    new_text = text if text is not None else f"I want to {item['english_text']} in this field."
    return client.post(
        f"/api/v1/essays/{essay['id']}/expression-suggestions/{suggestion['id']}/accept",
        json={
            "item_id": item["id"],
            "base_revision": base_revision,
            "client_revision": 2,
            "content_json": tiptap_doc(new_text),
            "plain_text": new_text,
            "word_count": len(new_text.split()),
            "modified_range": {"start": 0, "end": len(TEXT), "offset_unit": "unicode_codepoint"},
        },
        headers=headers,
    )


def test_accept_applies_document_atomically(client, db):
    headers, essay, session = _setup(client)
    suggestion = _polish(client, headers, essay, session).json()["data"]
    item = suggestion["items"][0]

    response = _accept(client, headers, essay, suggestion, item)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["server_revision"] == 3
    assert item["english_text"] in data["plain_text"]

    working = client.get(f"/api/v1/essays/{essay['id']}/working-document", headers=headers).json()[
        "data"
    ]
    assert working["server_revision"] == 3
    assert working["plain_text"] == data["plain_text"]

    events = list(db.execute(select(EssayEditEvent)).scalars())
    assert len(events) == 1
    assert events[0].event_type == "accept_suggestion"
    assert events[0].actor_type == "ai_accept"

    again = _accept(client, headers, essay, suggestion, item, base_revision=3)
    assert again.status_code == 409


def test_accept_requires_expression_in_document(client):
    headers, essay, session = _setup(client)
    suggestion = _polish(client, headers, essay, session).json()["data"]
    item = suggestion["items"][0]

    response = _accept(client, headers, essay, suggestion, item, text="Completely unrelated text.")
    assert response.status_code == 422


def test_accept_stale_revision_no_partial_write(client, db):
    headers, essay, session = _setup(client)
    suggestion = _polish(client, headers, essay, session).json()["data"]
    item = suggestion["items"][0]

    response = _accept(client, headers, essay, suggestion, item, base_revision=99)
    assert response.status_code == 409
    working = client.get(f"/api/v1/essays/{essay['id']}/working-document", headers=headers).json()[
        "data"
    ]
    assert working["server_revision"] == 2
    assert db.execute(select(EssayEditEvent)).scalars().first() is None


def test_accept_foreign_suggestion_not_found(client):
    owner_headers, essay, session = _setup(client)
    suggestion = _polish(client, owner_headers, essay, session).json()["data"]
    intruder = auth_headers(client, "expr-intruder@example.com")

    response = _accept(client, intruder, essay, suggestion, suggestion["items"][0])
    assert response.status_code == 404
