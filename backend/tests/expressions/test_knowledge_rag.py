"""Semantic RAG + extraction integration tests (mock embeddings/LLM).

Pipeline guarantees: user-scoped retrieval, rebuildable embeddings, immutable
version extraction, confirmation-before-save. Semantic QUALITY requires a real
embedding provider (evaluated separately); mock vectors verify the pipeline.
"""

from essay_helpers import auth_headers, create_essay, save_document
from sqlalchemy import select

from app.modules.analytics.models import AiUsageLog
from app.modules.expressions.models import ExpressionEmbedding


def _create_expression(client, headers, english, chinese=None):
    return client.post(
        "/api/v1/expressions",
        json={"english_text": english, "chinese_meaning": chinese},
        headers=headers,
    )


def test_create_expression_stores_embedding(client, db):
    headers = auth_headers(client)
    response = _create_expression(client, headers, "gain hands-on experience", "获得实践经验")
    assert response.status_code == 201, response.text
    expression_id = response.json()["data"]["id"]

    embeddings = list(db.execute(select(ExpressionEmbedding)).scalars())
    assert len(embeddings) == 1
    assert str(embeddings[0].expression_id) == expression_id
    assert embeddings[0].embedding_model == "mock-embedding-v1"
    assert embeddings[0].dimensions == 1536
    assert embeddings[0].content_hash


def test_duplicate_create_does_not_duplicate_embedding(client, db):
    headers = auth_headers(client)
    assert _create_expression(client, headers, "same expression").status_code == 201
    assert _create_expression(client, headers, "same expression").status_code == 409
    assert len(list(db.execute(select(ExpressionEmbedding)).scalars())) == 1


def test_semantic_search_is_user_scoped(client):
    owner = auth_headers(client, "rag-owner@example.com")
    intruder = auth_headers(client, "rag-intruder@example.com")
    assert _create_expression(client, owner, "gain hands-on experience").status_code == 201
    assert _create_expression(client, owner, "raise public awareness").status_code == 201

    owner_results = client.post(
        "/api/v1/expressions/search",
        json={"query": "experience", "mode": "semantic"},
        headers=owner,
    ).json()["data"]["items"]
    assert len(owner_results) == 2

    intruder_results = client.post(
        "/api/v1/expressions/search",
        json={"query": "experience", "mode": "semantic"},
        headers=intruder,
    ).json()["data"]["items"]
    assert intruder_results == []


def test_hybrid_search_merges_without_duplicates(client):
    headers = auth_headers(client)
    assert _create_expression(client, headers, "gain hands-on experience").status_code == 201

    results = client.post(
        "/api/v1/expressions/search",
        json={"query": "experience", "mode": "hybrid"},
        headers=headers,
    ).json()["data"]["items"]
    ids = [item["id"] for item in results]
    assert len(ids) == len(set(ids))
    assert len(ids) >= 1


def test_archived_and_deleted_excluded_from_semantic(client):
    headers = auth_headers(client)
    first = _create_expression(client, headers, "expression to archive").json()["data"]
    second = _create_expression(client, headers, "expression to delete").json()["data"]
    assert (
        client.post(f"/api/v1/expressions/{first['id']}/archive", headers=headers).status_code
        == 200
    )
    assert client.delete(f"/api/v1/expressions/{second['id']}", headers=headers).status_code == 204

    results = client.post(
        "/api/v1/expressions/search",
        json={"query": "expression", "mode": "semantic"},
        headers=headers,
    ).json()["data"]["items"]
    assert results == []


def test_extraction_from_immutable_version_returns_candidates(client, db):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    assert (
        save_document(
            client,
            headers,
            essay["id"],
            base_revision=1,
            paragraphs=("Students should gain hands-on experience before graduation.",),
        ).status_code
        == 200
    )
    snapshot = client.post(
        f"/api/v1/essays/{essay['id']}/snapshots",
        json={"source_revision": 2, "version_type": "checkpoint"},
        headers=headers,
    ).json()["data"]

    response = client.post(
        f"/api/v1/essays/{essay['id']}/expressions/extract",
        json={"version_id": snapshot["id"], "extraction_scope": "full"},
        headers=headers,
    )
    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["version_id"] == snapshot["id"]
    assert isinstance(data["candidates"], list)
    assert len(data["candidates"]) >= 1
    for candidate in data["candidates"]:
        assert candidate["english_text"]
        assert candidate["chinese_meaning"]
        assert candidate["learning_value_reason"]

    logs = list(db.execute(select(AiUsageLog)).scalars())
    assert any(log.feature == "learning_extract" for log in logs)

    # Nothing persisted until the user confirms.
    listing = client.get("/api/v1/expressions", headers=headers).json()["data"]
    assert listing["items"] == []


def test_extraction_requires_own_version(client):
    owner = auth_headers(client, "extract-owner@example.com")
    intruder = auth_headers(client, "extract-intruder@example.com")
    essay = create_essay(client, owner)

    response = client.post(
        f"/api/v1/essays/{essay['id']}/expressions/extract",
        json={"version_id": essay["original_version_id"], "extraction_scope": "full"},
        headers=intruder,
    )
    assert response.status_code == 404


def test_extraction_confirmed_candidate_saves_with_source(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    response = client.post(
        f"/api/v1/essays/{essay['id']}/expressions/extract",
        json={"version_id": essay["original_version_id"], "extraction_scope": "full"},
        headers=headers,
    )
    candidate = response.json()["data"]["candidates"][0]

    saved = client.post(
        "/api/v1/expressions",
        json={
            "english_text": candidate["english_text"],
            "chinese_meaning": candidate["chinese_meaning"],
            "learning_value_reason": candidate["learning_value_reason"],
            "source_type": "essay",
            "essay_id": essay["id"],
        },
        headers=headers,
    )
    assert saved.status_code == 201, saved.text
    assert saved.json()["data"]["status"] == "collected"
