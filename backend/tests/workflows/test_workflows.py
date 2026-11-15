"""Workflow integration tests (Slice 8): LangGraph runs pause for human
confirmation; resume applies results through business services. Mock LLM.
"""

import uuid

from essay_helpers import auth_headers, create_essay, save_document


def _create_workflow(client, headers, workflow_type, **extra):
    payload = {"workflow_type": workflow_type, "input": extra.pop("input", {})}
    payload.update(extra)
    response = client.post("/api/v1/workflows", json=payload, headers=headers)
    assert response.status_code == 202, response.text
    return response.json()["data"]["workflow_id"]


def _get(client, headers, workflow_id):
    response = client.get(f"/api/v1/workflows/{workflow_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _essay_with_version(client, headers):
    essay = create_essay(client, headers, writing_type="ielts_task2")
    response = save_document(
        client, headers, essay["id"], base_revision=1, paragraphs=("Technology helps learning.",)
    )
    assert response.status_code == 200
    snapshot = client.post(
        f"/api/v1/essays/{essay['id']}/snapshots",
        json={"version_type": "checkpoint", "source_revision": 2},
        headers=headers,
    )
    assert snapshot.status_code == 201
    return essay, snapshot.json()["data"]


def test_planner_runs_to_confirmation_with_events(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers, writing_type="ielts_task2")
    workflow_id = _create_workflow(
        client, headers, "writing_planner", essay_id=essay["id"], input={"viewpoint": "Agree"}
    )

    data = _get(client, headers, workflow_id)
    assert data["status"] == "awaiting_confirmation"
    assert data["result_json"]["outline"]["thesis_statement"]
    assert data["result_json"]["outline"]["sections"]

    events = client.get(f"/api/v1/workflows/{workflow_id}/events", headers=headers)
    steps = [e["step"] for e in events.json()["data"]["items"]]
    assert "retrieve_expressions" in steps
    assert "generate_outline" in steps
    assert "quality_check" in steps
    assert steps[-1] == "confirmation"


def test_planner_confirm_saves_confirmed_outline(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers, writing_type="ielts_task2")
    workflow_id = _create_workflow(
        client, headers, "writing_planner", essay_id=essay["id"], input={}
    )

    response = client.post(
        f"/api/v1/workflows/{workflow_id}/resume", json={"action": "confirm"}, headers=headers
    )
    assert response.status_code == 202
    data = response.json()["data"]
    assert data["status"] == "completed"
    outline_id = data["result_json"]["outcome"]["outline_id"]

    outline = client.get(f"/api/v1/outlines/{outline_id}", headers=headers).json()["data"]
    assert outline["status"] == "confirmed"
    assert outline["nodes"]
    assert outline["workflow_id"] == workflow_id


def test_planner_reject_and_revise(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    workflow_id = _create_workflow(
        client, headers, "writing_planner", essay_id=essay["id"], input={}
    )

    response = client.post(
        f"/api/v1/workflows/{workflow_id}/resume",
        json={"action": "revise", "input": {"instructions": "More body paragraphs"}},
        headers=headers,
    )
    assert response.status_code == 202
    assert response.json()["data"]["status"] == "running"
    # The re-run happens in the background; poll until it pauses again.
    assert _get(client, headers, workflow_id)["status"] == "awaiting_confirmation"

    response = client.post(
        f"/api/v1/workflows/{workflow_id}/resume", json={"action": "reject"}, headers=headers
    )
    assert response.status_code == 202
    data = response.json()["data"]
    assert data["status"] == "completed"
    assert data["result_json"]["outcome"]["rejected"] is True

    listing = client.get(f"/api/v1/essays/{essay['id']}/outlines", headers=headers)
    assert listing.json()["data"]["items"] == []


def test_resume_requires_awaiting_confirmation(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    workflow_id = _create_workflow(
        client, headers, "writing_planner", essay_id=essay["id"], input={}
    )
    client.post(
        f"/api/v1/workflows/{workflow_id}/resume", json={"action": "confirm"}, headers=headers
    )
    response = client.post(
        f"/api/v1/workflows/{workflow_id}/resume", json={"action": "confirm"}, headers=headers
    )
    assert response.status_code == 409


def test_cancel_lifecycle(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    workflow_id = _create_workflow(
        client, headers, "writing_planner", essay_id=essay["id"], input={}
    )
    response = client.post(f"/api/v1/workflows/{workflow_id}/cancel", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "cancelled"
    response = client.post(f"/api/v1/workflows/{workflow_id}/cancel", headers=headers)
    assert response.status_code == 409


def test_extractor_confirm_saves_expressions(client):
    headers = auth_headers(client)
    essay, version = _essay_with_version(client, headers)
    workflow_id = _create_workflow(
        client,
        headers,
        "learning_extractor",
        essay_id=essay["id"],
        input={"version_id": version["id"], "scope": "full"},
    )
    data = _get(client, headers, workflow_id)
    assert data["status"] == "awaiting_confirmation"
    assert data["result_json"]["candidates"]

    response = client.post(
        f"/api/v1/workflows/{workflow_id}/resume",
        json={"action": "confirm", "input": {"candidate_indices": [0]}},
        headers=headers,
    )
    assert response.status_code == 202
    outcome = response.json()["data"]["result_json"]["outcome"]
    assert len(outcome["saved_expression_ids"]) == 1

    listing = client.get("/api/v1/expressions", headers=headers)
    assert len(listing.json()["data"]["items"]) == 1


def test_study_planner_confirm(client):
    headers = auth_headers(client)
    workflow_id = _create_workflow(
        client, headers, "personalized_study_planner", input={"goal": "Band 7"}
    )
    data = _get(client, headers, workflow_id)
    assert data["status"] == "awaiting_confirmation"
    assert data["result_json"]["plan"]["suggestions"]

    response = client.post(
        f"/api/v1/workflows/{workflow_id}/resume", json={"action": "continue"}, headers=headers
    )
    assert response.status_code == 202
    assert response.json()["data"]["status"] == "completed"


def test_essay_required_and_ownership(client):
    headers_a = auth_headers(client, email="wf-a@example.com")
    headers_b = auth_headers(client, email="wf-b@example.com")

    response = client.post(
        "/api/v1/workflows",
        json={"workflow_type": "writing_planner", "input": {}},
        headers=headers_a,
    )
    assert response.status_code == 422

    essay = create_essay(client, headers_a)
    workflow_id = _create_workflow(
        client, headers_a, "writing_planner", essay_id=essay["id"], input={}
    )
    assert client.get(f"/api/v1/workflows/{workflow_id}", headers=headers_b).status_code == 404
    assert (
        client.post(
            f"/api/v1/workflows/{workflow_id}/resume",
            json={"action": "confirm"},
            headers=headers_b,
        ).status_code
        == 404
    )
    assert (
        client.get(f"/api/v1/workflows/{workflow_id}/events", headers=headers_b).status_code == 404
    )


def test_invalid_action_rejected(client):
    headers = auth_headers(client)
    essay = create_essay(client, headers)
    workflow_id = _create_workflow(
        client, headers, "writing_planner", essay_id=essay["id"], input={}
    )
    response = client.post(
        f"/api/v1/workflows/{workflow_id}/resume", json={"action": "explode"}, headers=headers
    )
    assert response.status_code == 422


def test_unknown_workflow_404(client):
    headers = auth_headers(client)
    assert client.get(f"/api/v1/workflows/{uuid.uuid4()}", headers=headers).status_code == 404
