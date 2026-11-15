"""Outline integration tests (Slice 8): generation, hierarchy, confirmation,
node CRUD, ownership. Mock LLM keeps generation deterministic.
"""

import uuid

from essay_helpers import auth_headers, create_essay

from app.ai import llm
from app.core.exceptions import ApiError
from app.modules.outlines.models import WritingOutline


def _generate(client, headers, essay_id, **payload):
    response = client.post(
        f"/api/v1/essays/{essay_id}/outlines/generate", json=payload, headers=headers
    )
    assert response.status_code == 202, response.text
    return response.json()["data"]["outline_id"]


def _get(client, headers, outline_id):
    response = client.get(f"/api/v1/outlines/{outline_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_generation_produces_draft_hierarchy(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers, writing_type="ielts_task2")
    outline_id = _generate(client, headers, essay["id"], viewpoint="Free public transport")

    data = _get(client, headers, outline_id)
    assert data["status"] == "draft"
    assert data["thesis_statement"]
    sections = [n for n in data["nodes"] if n["node_type"] == "section"]
    paragraphs = [n for n in data["nodes"] if n["node_type"] == "paragraph"]
    ideas = [n for n in data["nodes"] if n["node_type"] == "sentence_idea"]
    assert len(sections) >= 2
    assert paragraphs and ideas
    assert all(p["parent_id"] in {s["id"] for s in sections} for p in paragraphs)
    assert all(i["parent_id"] in {p["id"] for p in paragraphs} for i in ideas)


def test_regeneration_increments_version(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    first = _generate(client, headers, essay["id"])
    second = _generate(client, headers, essay["id"])
    listing = client.get(f"/api/v1/essays/{essay['id']}/outlines", headers=headers)
    items = listing.json()["data"]["items"]
    assert len(items) == 2
    assert {i["version_no"] for i in items} == {1, 2}
    assert items[0]["id"] == second  # newest first
    assert first != second


def test_patch_thesis_and_confirm_lifecycle(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    outline_id = _generate(client, headers, essay["id"])

    response = client.patch(
        f"/api/v1/outlines/{outline_id}",
        json={"thesis_statement": "My refined thesis."},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["thesis_statement"] == "My refined thesis."

    response = client.post(f"/api/v1/outlines/{outline_id}/confirm", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "confirmed"
    assert data["confirmed_at"] is not None

    # Confirmed outlines are locked.
    response = client.patch(
        f"/api/v1/outlines/{outline_id}",
        json={"thesis_statement": "Too late."},
        headers=headers,
    )
    assert response.status_code == 409
    assert client.post(f"/api/v1/outlines/{outline_id}/confirm", headers=headers).status_code == 409


def test_confirm_empty_outline_rejected(client, db):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    from app.modules.essays.models import Essay

    owner = db.get(Essay, uuid.UUID(essay["id"])).user_id
    outline = WritingOutline(
        essay_id=uuid.UUID(essay["id"]),
        user_id=owner,
        version_no=1,
        status="draft",
        source_context={},
    )
    db.add(outline)
    db.commit()

    response = client.post(f"/api/v1/outlines/{outline.id}/confirm", headers=headers)
    assert response.status_code == 409


def test_node_crud_and_cascade(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    outline_id = _generate(client, headers, essay["id"])

    section = client.post(
        f"/api/v1/outlines/{outline_id}/nodes",
        json={"node_type": "section", "title": "Extra section", "sort_order": 99},
        headers=headers,
    )
    assert section.status_code == 201
    section_id = section.json()["data"]["id"]

    paragraph = client.post(
        f"/api/v1/outlines/{outline_id}/nodes",
        json={
            "node_type": "paragraph",
            "title": "Extra paragraph",
            "parent_id": section_id,
        },
        headers=headers,
    )
    assert paragraph.status_code == 201
    paragraph_id = paragraph.json()["data"]["id"]

    response = client.patch(
        f"/api/v1/outlines/{outline_id}/nodes/{paragraph_id}",
        json={"title": "Renamed paragraph", "content": "Notes", "sort_order": 3},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["title"] == "Renamed paragraph"

    response = client.delete(f"/api/v1/outlines/{outline_id}/nodes/{section_id}", headers=headers)
    assert response.status_code == 204
    data = _get(client, headers, outline_id)
    remaining = {n["id"] for n in data["nodes"]}
    assert section_id not in remaining
    assert paragraph_id not in remaining  # cascade


def test_node_parent_must_belong_to_outline(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    outline_id = _generate(client, headers, essay["id"])
    response = client.post(
        f"/api/v1/outlines/{outline_id}/nodes",
        json={"node_type": "paragraph", "title": "Orphan", "parent_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert response.status_code == 404


def test_ownership(client):
    headers_a = auth_headers(client, email="outline-a@example.com")
    headers_b = auth_headers(client, email="outline-b@example.com")
    essay = create_essay(client, headers_a)
    outline_id = _generate(client, headers_a, essay["id"])

    assert client.get(f"/api/v1/outlines/{outline_id}", headers=headers_b).status_code == 404
    assert (
        client.post(f"/api/v1/outlines/{outline_id}/confirm", headers=headers_b).status_code == 404
    )
    assert (
        client.get(f"/api/v1/essays/{essay['id']}/outlines", headers=headers_b).status_code == 404
    )
    assert (
        client.post(
            f"/api/v1/essays/{essay['id']}/outlines/generate", json={}, headers=headers_b
        ).status_code
        == 404
    )


def test_generation_failure_marks_failed(client, monkeypatch):
    def failing_call_llm(**kwargs):
        raise ApiError(502, "LLM_PROVIDER_ERROR", "The AI service failed.")

    monkeypatch.setattr(llm, "call_llm", failing_call_llm)
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    outline_id = _generate(client, headers, essay["id"])
    data = _get(client, headers, outline_id)
    assert data["status"] == "failed"
    assert data["nodes"] == []


def test_nodes_locked_after_confirm(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    outline_id = _generate(client, headers, essay["id"])
    client.post(f"/api/v1/outlines/{outline_id}/confirm", headers=headers)
    response = client.post(
        f"/api/v1/outlines/{outline_id}/nodes",
        json={"node_type": "section", "title": "Too late"},
        headers=headers,
    )
    assert response.status_code == 409
