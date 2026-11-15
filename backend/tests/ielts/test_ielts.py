"""IELTS question bank integration tests (Slice 6).

Covers the published+licensed gate, filters, keyset pagination, tags, random,
favorites (idempotent, user-scoped) and the essays.question_id link.
"""

import uuid

from essay_helpers import auth_headers
from sqlalchemy import func, select

from app.modules.ielts.models import IeltsQuestion, QuestionTag
from app.modules.ielts.seed import seed_ielts
from app.modules.ielts.seed_data import SEED_QUESTIONS, SEED_TAGS

BANK_SIZE = len(SEED_QUESTIONS)


def _list(client, headers, **params):
    response = client.get("/api/v1/ielts/questions", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_seed_covers_all_question_types_and_topics():
    assert BANK_SIZE == 60
    task1_types = {q["question_type"] for q in SEED_QUESTIONS if q["task_type"] == "task1"}
    assert task1_types == {
        "line_graph",
        "bar_chart",
        "pie_chart",
        "table",
        "process",
        "map",
        "letter_formal",
        "letter_semi_formal",
        "letter_informal",
    }
    task2_types = {q["question_type"] for q in SEED_QUESTIONS if q["task_type"] == "task2"}
    assert task2_types == {
        "opinion",
        "discussion",
        "advantages_disadvantages",
        "problem_solution",
        "two_part",
    }
    used_tags = {tag for q in SEED_QUESTIONS for tag in q["tags"]}
    assert used_tags == {tag["slug"] for tag in SEED_TAGS}
    for question in SEED_QUESTIONS:
        assert question["prompt_translation"]


def test_list_returns_seeded_bank(client):
    headers = auth_headers(client)
    data = _list(client, headers, limit=100)
    assert len(data["items"]) == BANK_SIZE
    assert data["next_cursor"] is None
    assert data["limit"] == 100
    item = data["items"][0]
    assert item["is_favorited"] is False
    assert item["tags"]
    assert item["prompt_text"]
    assert item["created_at"]


def test_keyset_pagination_walks_the_whole_bank(client):
    headers = auth_headers(client)
    seen: list[str] = []
    cursor = None
    for _ in range(20):
        params = {"limit": 7}
        if cursor:
            params["cursor"] = cursor
        data = _list(client, headers, **params)
        seen.extend(item["id"] for item in data["items"])
        cursor = data["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == BANK_SIZE
    assert len(set(seen)) == BANK_SIZE


def test_filters(client):
    headers = auth_headers(client)

    data = _list(client, headers, task_type="task2", limit=100)
    assert len(data["items"]) == 33
    assert all(item["task_type"] == "task2" for item in data["items"])

    data = _list(client, headers, question_type="opinion", limit=100)
    assert len(data["items"]) == 7
    assert all(item["question_type"] == "opinion" for item in data["items"])

    data = _list(client, headers, topic="education", limit=100)
    assert data["items"]
    assert all(any(tag["slug"] == "education" for tag in item["tags"]) for item in data["items"])

    data = _list(client, headers, task_type="task1", question_type="letter_formal", limit=100)
    assert len(data["items"]) == 3

    data = _list(client, headers, topic="does-not-exist", limit=100)
    assert data["items"] == []


def test_invalid_cursor_and_limit(client):
    headers = auth_headers(client)
    response = client.get(
        "/api/v1/ielts/questions", params={"cursor": "not-a-cursor"}, headers=headers
    )
    assert response.status_code == 422
    response = client.get("/api/v1/ielts/questions", params={"limit": 0}, headers=headers)
    assert response.status_code == 422


def test_question_detail(client):
    headers = auth_headers(client)
    data = _list(client, headers, limit=1)
    question_id = data["items"][0]["id"]

    response = client.get(f"/api/v1/ielts/questions/{question_id}", headers=headers)
    assert response.status_code == 200
    question = response.json()["data"]
    assert question["id"] == question_id
    assert question["license_status"] == "original"
    assert question["source_type"] == "original"
    assert question["source_title"]


def test_unknown_question_404(client):
    headers = auth_headers(client)
    response = client.get(f"/api/v1/ielts/questions/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404


def test_unpublished_and_unlicensed_questions_are_hidden(client, db):
    hidden = []
    for license_status, published in [("original", False), ("restricted", True), ("pending", True)]:
        question = IeltsQuestion(
            task_type="task2",
            question_type="opinion",
            prompt_text=f"Hidden question {license_status} {published}",
            source_type="third_party",
            license_status=license_status,
            is_published=published,
        )
        db.add(question)
        hidden.append(question)
    db.commit()

    headers = auth_headers(client)
    data = _list(client, headers, limit=100)
    assert len(data["items"]) == BANK_SIZE
    hidden_ids = {str(q.id) for q in hidden}
    assert not hidden_ids & {item["id"] for item in data["items"]}

    for question in hidden:
        response = client.get(f"/api/v1/ielts/questions/{question.id}", headers=headers)
        assert response.status_code == 404

    for _ in range(10):
        response = client.get("/api/v1/ielts/questions/random", headers=headers)
        assert response.status_code == 200
        assert response.json()["data"]["id"] not in hidden_ids


def test_tags_with_counts(client):
    headers = auth_headers(client)
    response = client.get("/api/v1/ielts/tags", headers=headers)
    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert len(items) == len(SEED_TAGS)
    by_slug = {item["slug"]: item for item in items}
    expected_education = sum(1 for q in SEED_QUESTIONS if "education" in q["tags"])
    assert by_slug["education"]["question_count"] == expected_education
    assert all(item["question_count"] > 0 for item in items)


def test_random_returns_a_permitted_question(client):
    headers = auth_headers(client)
    response = client.get("/api/v1/ielts/questions/random", headers=headers)
    assert response.status_code == 200
    question = response.json()["data"]
    assert question["task_type"] in {"task1", "task2"}
    assert question["license_status"] == "original"


def test_favorite_lifecycle_is_idempotent(client):
    headers = auth_headers(client)
    data = _list(client, headers, limit=1)
    question_id = data["items"][0]["id"]

    response = client.post(f"/api/v1/ielts/questions/{question_id}/favorite", headers=headers)
    assert response.status_code == 201
    assert response.json()["data"] == {"question_id": question_id, "favorited": True}

    response = client.post(f"/api/v1/ielts/questions/{question_id}/favorite", headers=headers)
    assert response.status_code == 201

    detail = client.get(f"/api/v1/ielts/questions/{question_id}", headers=headers).json()["data"]
    assert detail["is_favorited"] is True
    listed = _list(client, headers, limit=100)
    assert next(i for i in listed["items"] if i["id"] == question_id)["is_favorited"] is True

    response = client.delete(f"/api/v1/ielts/questions/{question_id}/favorite", headers=headers)
    assert response.status_code == 204
    response = client.delete(f"/api/v1/ielts/questions/{question_id}/favorite", headers=headers)
    assert response.status_code == 204

    detail = client.get(f"/api/v1/ielts/questions/{question_id}", headers=headers).json()["data"]
    assert detail["is_favorited"] is False


def test_favorite_unknown_question_404(client):
    headers = auth_headers(client)
    unknown = uuid.uuid4()
    response = client.post(f"/api/v1/ielts/questions/{unknown}/favorite", headers=headers)
    assert response.status_code == 404
    response = client.delete(f"/api/v1/ielts/questions/{unknown}/favorite", headers=headers)
    assert response.status_code == 404


def test_favorites_are_user_scoped(client):
    headers_a = auth_headers(client, email="ielts-a@example.com")
    headers_b = auth_headers(client, email="ielts-b@example.com")
    data = _list(client, headers_a, limit=1)
    question_id = data["items"][0]["id"]

    client.post(f"/api/v1/ielts/questions/{question_id}/favorite", headers=headers_a)
    response = client.get(f"/api/v1/ielts/questions/{question_id}", headers=headers_b)
    assert response.json()["data"]["is_favorited"] is False


def test_all_routes_require_auth(client):
    question_id = uuid.uuid4()
    assert client.get("/api/v1/ielts/questions").status_code == 401
    assert client.get(f"/api/v1/ielts/questions/{question_id}").status_code == 401
    assert client.get("/api/v1/ielts/questions/random").status_code == 401
    assert client.get("/api/v1/ielts/tags").status_code == 401
    assert client.post(f"/api/v1/ielts/questions/{question_id}/favorite").status_code == 401
    assert client.delete(f"/api/v1/ielts/questions/{question_id}/favorite").status_code == 401


def test_create_essay_from_question_autofills_prompt(client):
    headers = auth_headers(client)
    data = _list(client, headers, task_type="task2", limit=1)
    question = data["items"][0]

    response = client.post(
        "/api/v1/essays",
        json={
            "writing_type": "ielts_task2",
            "title": "Bank practice",
            "question_id": question["id"],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    essay = response.json()["data"]
    assert essay["question_id"] == question["id"]
    assert essay["question_prompt"] == question["prompt_text"]


def test_create_essay_rejects_mismatched_or_unknown_question(client):
    headers = auth_headers(client)
    data = _list(client, headers, task_type="task1", limit=1)
    question = data["items"][0]

    response = client.post(
        "/api/v1/essays",
        json={"writing_type": "ielts_task2", "question_id": question["id"]},
        headers=headers,
    )
    assert response.status_code == 422

    response = client.post(
        "/api/v1/essays",
        json={"writing_type": "ielts_task2", "question_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert response.status_code == 404


def test_seed_is_idempotent(db):
    seed_ielts(db)
    db.commit()
    assert db.execute(select(func.count(IeltsQuestion.id))).scalar() == BANK_SIZE
    assert db.execute(select(func.count(QuestionTag.id))).scalar() == len(SEED_TAGS)
