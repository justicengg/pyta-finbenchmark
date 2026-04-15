from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routers import pm_webhook
from app.db import Base, get_db


def build_test_client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(pm_webhook.router, prefix="/api")

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


SAMPLE_PAYLOAD = {
    "event": "primary_run_completed",
    "sandbox_id": "test-sandbox-001",
    "company_name": "Cursor (Anysphere)",
    "sector": "AI Developer Tools",
    "generated_at": "2026-04-15T00:00:00Z",
    "decision": "invest",
    "confidence": 0.87,
    "decision_rationale": "Strong product-market fit",
    "overall_verdict": "invest with conviction",
    "monitoring_triggers": [{"trigger": "ARR drops below 50M"}],
    "uncertainty_map": {"market_type": "BLUE_OCEAN", "assessments": {}},
    "founder_analysis": {"archetype": "technical"},
    "key_assumptions": {"items": []},
    "financial_lens": {"arr": 100_000_000},
    "path_forks": [{"fork_id": "f1", "trigger": "unverified_hard"}],
    "active_dimensions": ["market_validity", "team_execution"],
}


def test_create_pm_eval_case():
    client = build_test_client()
    resp = client.post(
        "/api/webhook/primary-run-completed",
        json=SAMPLE_PAYLOAD,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "created"
    assert "case_id" in body


def test_idempotency():
    client = build_test_client()
    resp1 = client.post(
        "/api/webhook/primary-run-completed",
        json=SAMPLE_PAYLOAD,
    )
    assert resp1.json()["status"] == "created"
    case_id = resp1.json()["case_id"]

    resp2 = client.post(
        "/api/webhook/primary-run-completed",
        json=SAMPLE_PAYLOAD,
    )
    assert resp2.json()["status"] == "already_exists"
    assert resp2.json()["case_id"] == case_id


def test_wrong_event_type():
    client = build_test_client()
    payload = {**SAMPLE_PAYLOAD, "event": "wrong_event"}
    resp = client.post(
        "/api/webhook/primary-run-completed",
        json=payload,
    )
    assert resp.status_code == 400


def test_invalid_secret(monkeypatch):
    monkeypatch.setattr(
        "app.api.routers.pm_webhook.settings",
        type("S", (), {"main_backend_webhook_secret": "real-secret"})(),
    )
    client = build_test_client()
    resp = client.post(
        "/api/webhook/primary-run-completed",
        json=SAMPLE_PAYLOAD,
        headers={"X-Webhook-Secret": "wrong-secret"},
    )
    assert resp.status_code == 401


def test_report_snapshot_contains_full_payload():
    client = build_test_client()
    resp = client.post(
        "/api/webhook/primary-run-completed",
        json=SAMPLE_PAYLOAD,
    )
    assert resp.json()["status"] == "created"
    assert resp.json()["case_id"] is not None
