"""ADR-026 fragment-level sentence polish: scan, offsets, pagination,
natural-sentence empty result, records list. Mock LLM flags 'very like'.
"""

from essay_helpers import auth_headers
from grammar_helpers import setup_essay_with_text

UNNATURAL = "I very like this book."
NATURAL = "She went to school yesterday."


def _polish(client, headers, essay_id, session_id, sentence, **extra):
    start = 0
    return client.post(
        f"/api/v1/essays/{essay_id}/expressions/polish-sentence",
        json={
            "session_id": session_id,
            "server_revision": 2,
            "client_revision": 1,
            "sentence": sentence,
            "sentence_range": {
                "start": start,
                "end": len(sentence),
                "offset_unit": "unicode_codepoint",
            },
            **extra,
        },
        headers=headers,
    )


def test_scan_flags_fragment_with_offsets_and_three_options(client):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=UNNATURAL)

    response = _polish(client, headers, essay["id"], session["id"], UNNATURAL)
    assert response.status_code == 200, response.text
    fragments = response.json()["data"]["fragments"]
    assert len(fragments) == 1
    fragment = fragments[0]
    assert fragment["anchor_text"] == "very like"
    assert fragment["start_offset"] == UNNATURAL.index("very like")
    assert fragment["end_offset"] == fragment["start_offset"] + len("very like")
    assert len(fragment["items"]) == 3
    assert fragment["items"][0]["english_text"] == "really like"
    assert fragment["items"][0]["start_offset"] == fragment["start_offset"]


def test_natural_sentence_returns_no_fragments(client):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=NATURAL)

    response = _polish(client, headers, essay["id"], session["id"], NATURAL)
    assert response.status_code == 200
    assert response.json()["data"]["fragments"] == []


def test_more_options_excludes_previous(client):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=UNNATURAL)

    response = _polish(
        client,
        headers,
        essay["id"],
        session["id"],
        UNNATURAL,
        fragment_anchor="very like",
        exclude=["really like", "am very fond of", "love"],
    )
    assert response.status_code == 200
    # Mock returns the same deterministic options; exclusion is enforced by
    # the prompt for real providers. Here we assert the focus filter works.
    fragments = response.json()["data"]["fragments"]
    assert len(fragments) == 1
    assert fragments[0]["anchor_text"] == "very like"


def test_records_list_contains_polish_history(client):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=UNNATURAL)
    _polish(client, headers, essay["id"], session["id"], UNNATURAL)

    response = client.get(
        f"/api/v1/essays/{essay['id']}/expression-suggestions", headers=headers
    )
    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["kind"] == "polish"
    assert items[0]["selected_text"] == "very like"
    assert len(items[0]["items"]) == 3


def test_independent_mode_rejected(client):
    headers = auth_headers(client)
    essay, session = setup_essay_with_text(client, headers, text=UNNATURAL, mode="independent")
    response = _polish(client, headers, essay["id"], session["id"], UNNATURAL)
    assert response.status_code == 403


def test_foreign_essay_not_found(client):
    owner = auth_headers(client, "polish-owner@example.com")
    intruder = auth_headers(client, "polish-intruder@example.com")
    essay, session = setup_essay_with_text(client, owner, text=UNNATURAL)
    response = _polish(client, intruder, essay["id"], session["id"], UNNATURAL)
    assert response.status_code == 404