"""Billing integration tests (Slice 10): plans, sandbox checkout/confirm,
cancellation, quota metering/enforcement, history scoping. ADR-021.
"""

import uuid
from datetime import date

from essay_helpers import auth_headers, create_essay, save_document
from sqlalchemy import select

from app.modules.billing.models import UsageMeter


def _checkout(client, headers, plan_code="pro", key=None):
    extra = {"Idempotency-Key": key} if key else {}
    return client.post(
        "/api/v1/billing/checkout",
        json={"plan_code": plan_code},
        headers={**headers, **extra},
    )


def _upgrade(client, headers, plan_code="pro"):
    checkout = _checkout(client, headers, plan_code)
    assert checkout.status_code == 201, checkout.text
    transaction_id = checkout.json()["data"]["transaction_id"]
    confirm = client.post(
        "/api/v1/billing/confirm", json={"transaction_id": transaction_id}, headers=headers
    )
    assert confirm.status_code == 200, confirm.text
    return confirm.json()["data"]


def _evaluation_once(client, headers):
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
    return client.post(
        f"/api/v1/essays/{essay['id']}/evaluations",
        json={
            "version_id": snapshot.json()["data"]["id"],
            "evaluation_type": "ielts",
            "task_type": "task2",
        },
        headers=headers,
    )


def test_plans_seeded(client):
    headers = auth_headers(client)
    response = client.get("/api/v1/billing/plans", headers=headers)
    assert response.status_code == 200
    items = response.json()["data"]["items"]
    codes = {item["code"] for item in items}
    assert codes == {"free", "pro", "ultimate"}
    by_code = {item["code"]: item for item in items}
    assert float(by_code["free"]["price_monthly"]) == 0.0
    assert by_code["ultimate"]["quota_ai_calls_monthly"] is None


def test_default_subscription_is_free(client):
    headers = auth_headers(client)
    response = client.get("/api/v1/billing/subscription", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["plan_code"] == "free"
    assert data["status"] == "active"
    assert data["cancelled_at"] is None


def test_sandbox_checkout_confirm_upgrades(client):
    headers = auth_headers(client)
    checkout = _checkout(client, headers)
    data = checkout.json()["data"]
    assert data["provider"] == "sandbox"
    assert data["status"] == "pending"
    assert float(data["amount"]) == 19.0

    confirm = client.post(
        "/api/v1/billing/confirm",
        json={"transaction_id": data["transaction_id"]},
        headers=headers,
    )
    assert confirm.status_code == 200
    subscription = confirm.json()["data"]
    assert subscription["plan_code"] == "pro"
    assert subscription["status"] == "active"

    history = client.get("/api/v1/billing/history", headers=headers)
    items = history.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["status"] == "succeeded"
    assert items[0]["completed_at"] is not None


def test_checkout_validation(client):
    headers = auth_headers(client)
    assert _checkout(client, headers, "free").status_code == 422
    assert _checkout(client, headers, "does-not-exist").status_code == 404


def test_confirm_lifecycle_and_ownership(client):
    headers_a = auth_headers(client, email="bill-a@example.com")
    headers_b = auth_headers(client, email="bill-b@example.com")
    transaction_id = _checkout(client, headers_a).json()["data"]["transaction_id"]

    assert (
        client.post(
            "/api/v1/billing/confirm",
            json={"transaction_id": transaction_id},
            headers=headers_b,
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/billing/confirm", json={"transaction_id": str(uuid.uuid4())}, headers=headers_a
        ).status_code
        == 404
    )
    first = client.post(
        "/api/v1/billing/confirm", json={"transaction_id": transaction_id}, headers=headers_a
    )
    assert first.status_code == 200
    second = client.post(
        "/api/v1/billing/confirm", json={"transaction_id": transaction_id}, headers=headers_a
    )
    assert second.status_code == 409


def test_cancel_lifecycle(client):
    headers = auth_headers(client)
    assert client.post("/api/v1/billing/cancel", headers=headers).status_code == 409  # free

    _upgrade(client, headers)
    response = client.post("/api/v1/billing/cancel", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "cancelled"
    assert data["cancelled_at"] is not None
    # Access continues until period end.
    assert data["plan_code"] == "pro"
    assert client.post("/api/v1/billing/cancel", headers=headers).status_code == 409


def test_usage_metering_counts_llm_calls_and_evaluations(client):
    headers = auth_headers(client)
    response = _evaluation_once(client, headers)
    assert response.status_code == 202

    usage = client.get("/api/v1/billing/usage", headers=headers).json()["data"]
    assert usage["plan_code"] == "free"
    assert usage["ai_calls"] >= 1
    assert usage["evaluations"] == 1
    assert usage["quota_ai_calls_monthly"] == 100
    assert usage["period_start"] == date.today().replace(day=1).isoformat()


def _set_meter(db, ai_calls=0, evaluations=0):
    meter = db.execute(select(UsageMeter)).scalars().first()
    meter.ai_calls = ai_calls
    meter.evaluations = evaluations
    db.commit()


def test_ai_quota_enforced(client, db):
    headers = auth_headers(client)
    client.get("/api/v1/billing/usage", headers=headers)  # materialize meter
    _set_meter(db, ai_calls=100)
    response = _evaluation_once(client, headers)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "QUOTA_EXCEEDED"


def test_evaluation_quota_enforced(client, db):
    headers = auth_headers(client)
    client.get("/api/v1/billing/usage", headers=headers)
    _set_meter(db, evaluations=10)
    response = _evaluation_once(client, headers)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "QUOTA_EXCEEDED"


def test_upgrade_lifts_quota(client, db):
    headers = auth_headers(client)
    client.get("/api/v1/billing/usage", headers=headers)
    _set_meter(db, ai_calls=100, evaluations=10)
    assert _evaluation_once(client, headers).status_code == 429

    _upgrade(client, headers)
    assert _evaluation_once(client, headers).status_code == 202


def test_history_is_user_scoped(client):
    headers_a = auth_headers(client, email="hist-a@example.com")
    headers_b = auth_headers(client, email="hist-b@example.com")
    _upgrade(client, headers_a)
    assert client.get("/api/v1/billing/history", headers=headers_b).json()["data"]["items"] == []


def test_checkout_idempotency(client):
    headers = auth_headers(client)
    first = _checkout(client, headers, key="billing-key-1")
    second = _checkout(client, headers, key="billing-key-1")
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["data"]["transaction_id"] == second.json()["data"]["transaction_id"]


def test_billing_requires_auth(client):
    assert client.get("/api/v1/billing/plans").status_code == 401
    assert client.get("/api/v1/billing/subscription").status_code == 401
    assert client.post("/api/v1/billing/checkout", json={"plan_code": "pro"}).status_code == 401
    response = client.post(
        "/api/v1/billing/confirm", json={"transaction_id": str(uuid.uuid4())}
    )
    assert response.status_code == 401
    assert client.post("/api/v1/billing/cancel").status_code == 401
    assert client.get("/api/v1/billing/history").status_code == 401
    assert client.get("/api/v1/billing/usage").status_code == 401
