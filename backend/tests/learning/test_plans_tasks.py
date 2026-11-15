"""Learning plans/tasks tests (Slice 9): CRUD, task lifecycle, planner hook."""

import uuid

from essay_helpers import auth_headers


def test_create_and_list_plans(client):
    headers = auth_headers(client)
    response = client.post(
        "/api/v1/learning/plans",
        json={"title": "Band 7 in 3 months", "goal": "Improve writing", "daily_target_minutes": 30},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    plan = response.json()["data"]
    assert plan["status"] == "active"
    assert plan["daily_target_minutes"] == 30

    listing = client.get("/api/v1/learning/plans", headers=headers)
    assert listing.status_code == 200
    assert len(listing.json()["data"]["items"]) == 1


def test_plan_validation(client):
    headers = auth_headers(client)
    response = client.post("/api/v1/learning/plans", json={"title": ""}, headers=headers)
    assert response.status_code == 422
    response = client.post(
        "/api/v1/learning/plans",
        json={"title": "Bad dates", "start_date": "2026-03-01", "end_date": "2026-02-01"},
        headers=headers,
    )
    assert response.status_code == 422
    response = client.post(
        "/api/v1/learning/plans",
        json={"title": "Bad target", "daily_target_minutes": 0},
        headers=headers,
    )
    assert response.status_code == 422


def test_study_planner_confirm_creates_plan_and_tasks(client):
    headers = auth_headers(client)
    response = client.post(
        "/api/v1/workflows",
        json={"workflow_type": "personalized_study_planner", "input": {"goal": "Band 7"}},
        headers=headers,
    )
    workflow_id = response.json()["data"]["workflow_id"]
    response = client.post(
        f"/api/v1/workflows/{workflow_id}/resume", json={"action": "confirm"}, headers=headers
    )
    assert response.status_code == 202
    outcome = response.json()["data"]["result_json"]["outcome"]
    assert outcome["plan_id"]
    assert outcome["task_count"] >= 2

    plans = client.get("/api/v1/learning/plans", headers=headers).json()["data"]["items"]
    assert len(plans) == 1
    assert plans[0]["goal"] == "Band 7"

    tasks = client.get("/api/v1/learning/tasks", headers=headers).json()["data"]["items"]
    assert len(tasks) == outcome["task_count"]
    assert all(t["plan_id"] == outcome["plan_id"] for t in tasks)
    assert all(t["status"] == "pending" for t in tasks)
    assert {t["task_type"] for t in tasks} <= {"review", "practice", "writing"}


def test_task_completion_lifecycle(client):
    headers = auth_headers(client)
    response = client.post(
        "/api/v1/workflows",
        json={"workflow_type": "personalized_study_planner", "input": {}},
        headers=headers,
    )
    workflow_id = response.json()["data"]["workflow_id"]
    client.post(
        f"/api/v1/workflows/{workflow_id}/resume", json={"action": "confirm"}, headers=headers
    )
    task = client.get("/api/v1/learning/tasks", headers=headers).json()["data"]["items"][0]

    response = client.patch(
        f"/api/v1/learning/tasks/{task['id']}", json={"status": "completed"}, headers=headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "completed"
    assert data["completed_at"] is not None

    response = client.patch(
        f"/api/v1/learning/tasks/{task['id']}", json={"status": "pending"}, headers=headers
    )
    assert response.json()["data"]["completed_at"] is None

    response = client.patch(
        f"/api/v1/learning/tasks/{task['id']}",
        json={"title": "Renamed task", "status": "in_progress"},
        headers=headers,
    )
    assert response.json()["data"]["title"] == "Renamed task"


def test_task_ownership_and_validation(client):
    headers_a = auth_headers(client, email="plan-a@example.com")
    headers_b = auth_headers(client, email="plan-b@example.com")
    response = client.post(
        "/api/v1/workflows",
        json={"workflow_type": "personalized_study_planner", "input": {}},
        headers=headers_a,
    )
    workflow_id = response.json()["data"]["workflow_id"]
    client.post(
        f"/api/v1/workflows/{workflow_id}/resume", json={"action": "confirm"}, headers=headers_a
    )
    task = client.get("/api/v1/learning/tasks", headers=headers_a).json()["data"]["items"][0]

    assert (
        client.patch(
            f"/api/v1/learning/tasks/{task['id']}", json={"status": "completed"}, headers=headers_b
        ).status_code
        == 404
    )
    assert client.get("/api/v1/learning/tasks", headers=headers_b).json()["data"]["items"] == []
    assert client.get("/api/v1/learning/plans", headers=headers_b).json()["data"]["items"] == []
    response = client.patch(
        f"/api/v1/learning/tasks/{uuid.uuid4()}",
        json={"status": "completed"},
        headers=headers_a,
    )
    assert response.status_code == 404
    assert (
        client.patch(
            f"/api/v1/learning/tasks/{task['id']}", json={"status": "exploded"}, headers=headers_a
        ).status_code
        == 422
    )
