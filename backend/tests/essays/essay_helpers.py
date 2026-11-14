"""Shared helpers for essay integration tests."""

PASSWORD = "SecurePassword123"


def auth_headers(client, email="essay-user@example.com") -> dict:
    response = client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def create_essay(client, headers, **overrides) -> dict:
    payload = {"writing_type": "free_writing", "title": "My essay"}
    payload.update(overrides)
    response = client.post("/api/v1/essays", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def tiptap_doc(*paragraphs: str) -> dict:
    """TipTap document with one paragraph per argument (empty = empty doc)."""
    return {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text}]}
            for text in paragraphs
        ],
    }


def plain_text_of(*paragraphs: str) -> str:
    return "\n\n".join(paragraphs)


def save_document(
    client,
    headers,
    essay_id,
    *,
    base_revision: int,
    paragraphs: tuple[str, ...] = ("Hello world.",),
    client_revision: int = 1,
    include_client_values: bool = True,
):
    text = plain_text_of(*paragraphs)
    payload = {
        "base_revision": base_revision,
        "client_revision": client_revision,
        "content_json": tiptap_doc(*paragraphs),
    }
    if include_client_values:
        payload["plain_text"] = text
        payload["word_count"] = len(text.split())
    return client.put(f"/api/v1/essays/{essay_id}/working-document", json=payload, headers=headers)
