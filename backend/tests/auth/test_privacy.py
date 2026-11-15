"""Account deletion & export tests (Slice 11, R9).

Deletion must remove every owned row across all domains while leaving
system reference data (IELTS bank, subscription plans) intact.
"""

from essay_helpers import auth_headers, create_essay, save_document
from sqlalchemy import func, select

from app.modules.auth.models import AuthSession
from app.modules.billing.models import SubscriptionPlan, UserSubscription
from app.modules.essays.models import Essay, EssayVersion
from app.modules.expressions.models import UserExpression
from app.modules.ielts.models import IeltsQuestion
from app.modules.learning.models import LearningPlan
from app.modules.users.models import User, UserProfile


def _seed_user_data(client, headers):
    essay = create_essay(client, headers, writing_type="ielts_task2")
    save_document(client, headers, essay["id"], base_revision=1, paragraphs=("Hello world.",))
    client.post(
        f"/api/v1/essays/{essay['id']}/snapshots",
        json={"version_type": "checkpoint", "source_revision": 2},
        headers=headers,
    )
    client.post(
        "/api/v1/expressions",
        json={"english_text": "gain experience", "chinese_meaning": "获得经验"},
        headers=headers,
    )
    client.post("/api/v1/learning/plans", json={"title": "My plan"}, headers=headers)
    client.get("/api/v1/billing/subscription", headers=headers)  # materialize free tier
    return essay


def test_export_contains_owned_data(client):
    headers = auth_headers(client, email="export@example.com")
    _seed_user_data(client, headers)

    response = client.get("/api/v1/users/me/export", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["account"]["email"] == "export@example.com"
    assert len(data["essays"]) == 1
    assert len(data["essay_versions"]) >= 2  # original + checkpoint
    assert len(data["working_documents"]) == 1
    assert len(data["expressions"]) == 1
    assert len(data["learning_plans"]) == 1
    assert len(data["subscription"]) == 1
    assert "password_hash" not in str(data)


def test_export_requires_auth(client):
    assert client.get("/api/v1/users/me/export").status_code == 401


def test_delete_account_removes_everything(client, db):
    headers = auth_headers(client, email="delete-me@example.com")
    _seed_user_data(client, headers)
    user = db.execute(select(User).where(User.email == "delete-me@example.com")).scalar_one()
    uid = user.id

    bank_count = db.execute(select(func.count(IeltsQuestion.id))).scalar_one()
    plan_count = db.execute(select(func.count(SubscriptionPlan.id))).scalar_one()

    response = client.delete("/api/v1/users/me", headers=headers)
    assert response.status_code == 204
    db.expire_all()  # the request session deleted rows; drop cached identities

    def _first(model, **filters):
        statement = select(model)
        for column, value in filters.items():
            statement = statement.where(getattr(model, column) == value)
        return db.execute(statement).scalars().first()

    assert db.get(User, uid) is None
    assert _first(UserProfile, user_id=uid) is None
    assert _first(Essay, user_id=uid) is None
    assert db.execute(select(EssayVersion)).scalars().first() is None
    assert _first(UserExpression, user_id=uid) is None
    assert _first(LearningPlan, user_id=uid) is None
    assert _first(UserSubscription, user_id=uid) is None
    assert _first(AuthSession, user_id=uid) is None

    # System reference data survives.
    assert db.execute(select(func.count(IeltsQuestion.id))).scalar_one() == bank_count
    assert db.execute(select(func.count(SubscriptionPlan.id))).scalar_one() == plan_count

    # The deleted account can no longer authenticate.
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "delete-me@example.com", "password": "SecurePassword123"},
    )
    assert login.status_code == 401


def test_delete_account_is_isolated_per_user(client, db):
    headers_a = auth_headers(client, email="keep-a@example.com")
    headers_b = auth_headers(client, email="keep-b@example.com")
    _seed_user_data(client, headers_a)
    essay_b = create_essay(client, headers_b)

    assert client.delete("/api/v1/users/me", headers=headers_a).status_code == 204
    # User B's data is untouched.
    assert client.get(f"/api/v1/essays/{essay_b['id']}", headers=headers_b).status_code == 200


def test_delete_requires_auth(client):
    assert client.delete("/api/v1/users/me").status_code == 401
