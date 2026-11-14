"""Shared helpers for grammar integration tests."""

from essay_helpers import auth_headers, create_essay, save_document  # noqa: F401


def start_session(client, headers, essay_id, mode="assisted") -> dict:
    response = client.post(
        f"/api/v1/essays/{essay_id}/sessions",
        json={"mode": mode, "activity_type": "practice"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def setup_essay_with_text(client, headers, text="He go to school yesterday.", mode="assisted"):
    essay = create_essay(client, headers)
    response = save_document(client, headers, essay["id"], base_revision=1, paragraphs=(text,))
    assert response.status_code == 200, response.text
    session = start_session(client, headers, essay["id"], mode=mode)
    return essay, session


def check_text(client, headers, essay_id, session_id, text, *, revision=2, start=0):
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
        },
        headers=headers,
    )


def first_issue(client, headers, essay_id, session_id, text, **kwargs) -> dict:
    response = check_text(client, headers, essay_id, session_id, text, **kwargs)
    assert response.status_code == 200, response.text
    return response.json()["data"]["issues"][0]


def all_issues(client, headers, essay_id, session_id, text, **kwargs) -> list[dict]:
    response = check_text(client, headers, essay_id, session_id, text, **kwargs)
    assert response.status_code == 200, response.text
    return response.json()["data"]["issues"]
