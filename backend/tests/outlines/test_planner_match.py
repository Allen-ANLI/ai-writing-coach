"""Ghost position + embedding match tests (ADR-033). Mock embeddings degrade
to pure position; a stubbed real provider exercises cosine gating."""

from essay_helpers import auth_headers, create_essay

from app.ai.embeddings import EmbeddingResult
from app.core.config import get_settings
from app.modules.outlines import chat


def _match(client, headers, essay_id, sentences, hints):
    return client.post(
        f"/api/v1/essays/{essay_id}/planner/match",
        json={"sentences": sentences, "hints": hints},
        headers=headers,
    )


def test_mock_degrades_to_position(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    response = _match(
        client, headers, essay["id"], ["First sentence.", "Second sentence."], ["h1", "h2", "h3"]
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    # mock has no semantics → matched = min(sentences, hints) = 2 (position).
    assert data == {"matched": 2, "degraded": True}


def test_empty_sentences_match_zero(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    data = _match(client, headers, essay["id"], [], ["h1"]).json()["data"]
    assert data["matched"] == 0


def test_deletion_retreats_position(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    hints = ["h1", "h2", "h3"]
    three = _match(client, headers, essay["id"], ["s1.", "s2.", "s3."], hints).json()["data"]
    assert three["matched"] == 3
    # Deleting back to one sentence retreats the index (position-based).
    one = _match(client, headers, essay["id"], ["s1."], hints).json()["data"]
    assert one["matched"] == 1


def test_real_embedding_cosine_gating(client, monkeypatch):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    monkeypatch.setattr(get_settings(), "embedding_provider", "openai_compat")

    def fake_embed(texts):
        # texts = [s0, s1, h0, h1]; s0 matches h0, s1 orthogonal to h1.
        vectors = [[1.0, 0.0], [1.0, 0.0], [1.0, 0.0], [0.0, 1.0]]
        return EmbeddingResult(vectors=vectors, model_name="stub", provider="openai_compat")

    monkeypatch.setattr(chat, "embed_texts", fake_embed)
    data = _match(
        client, headers, essay["id"], ["s0.", "s1."], ["h0", "h1"]
    ).json()["data"]
    # Leading match stops at the first non-matching pair (index 1).
    assert data == {"matched": 1, "degraded": False}


def test_real_embedding_failure_degrades(client, monkeypatch):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    monkeypatch.setattr(get_settings(), "embedding_provider", "openai_compat")

    def failing_embed(texts):
        from app.core.exceptions import ApiError

        raise ApiError(502, "LLM_PROVIDER_ERROR", "embedding down")

    monkeypatch.setattr(chat, "embed_texts", failing_embed)
    data = _match(client, headers, essay["id"], ["s0.", "s1."], ["h0", "h1"]).json()["data"]
    assert data == {"matched": 2, "degraded": True}


def test_match_ownership(client):
    owner = auth_headers(client, email="match-owner@example.com")
    intruder = auth_headers(client, email="match-intruder@example.com")
    essay = create_essay(client, owner)
    assert _match(client, intruder, essay["id"], ["s1."], ["h1"]).status_code == 404