"""AI usage analytics tests (Slice 9): totals, by-feature, trends, scoping."""

from essay_helpers import auth_headers, create_essay, save_document


def _run_evaluation(client, headers):
    essay = create_essay(client, headers, writing_type="ielts_task2")
    response = save_document(
        client, headers, essay["id"], base_revision=1, paragraphs=("Some essay text.",)
    )
    assert response.status_code == 200
    snapshot = client.post(
        f"/api/v1/essays/{essay['id']}/snapshots",
        json={"version_type": "checkpoint", "source_revision": 2},
        headers=headers,
    )
    assert snapshot.status_code == 201
    response = client.post(
        f"/api/v1/essays/{essay['id']}/evaluations",
        json={
            "version_id": snapshot.json()["data"]["id"],
            "evaluation_type": "ielts",
            "task_type": "task2",
        },
        headers=headers,
    )
    assert response.status_code == 202


def test_usage_totals_and_features(client):
    headers = auth_headers(client)
    _run_evaluation(client, headers)
    _run_evaluation(client, headers)

    response = client.get("/api/v1/analytics/ai-usage", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_calls"] == 2
    assert data["success_calls"] == 2
    assert data["error_calls"] == 0
    assert data["input_tokens"] > 0
    assert data["output_tokens"] > 0
    assert data["estimated_cost"] == 0.0  # mock provider is free

    response = client.get("/api/v1/analytics/ai-usage/by-feature", headers=headers)
    items = response.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["feature"] == "ielts_evaluate_task2"
    assert items[0]["calls"] == 2


def test_trends_cover_fourteen_days(client):
    headers = auth_headers(client)
    _run_evaluation(client, headers)
    response = client.get("/api/v1/analytics/ai-usage/trends", headers=headers)
    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert len(items) == 14
    assert items[-1]["calls"] == 1
    assert sum(point["calls"] for point in items) == 1
    assert all("date" in point for point in items)


def test_usage_is_user_scoped(client):
    headers_a = auth_headers(client, email="usage-a@example.com")
    headers_b = auth_headers(client, email="usage-b@example.com")
    _run_evaluation(client, headers_a)

    data = client.get("/api/v1/analytics/ai-usage", headers=headers_b).json()["data"]
    assert data["total_calls"] == 0
    assert data["estimated_cost"] == 0.0
    items = client.get("/api/v1/analytics/ai-usage/by-feature", headers=headers_b).json()["data"]
    assert items["items"] == []


def test_analytics_requires_auth(client):
    assert client.get("/api/v1/analytics/ai-usage").status_code == 401
    assert client.get("/api/v1/analytics/ai-usage/by-feature").status_code == 401
    assert client.get("/api/v1/analytics/ai-usage/trends").status_code == 401
