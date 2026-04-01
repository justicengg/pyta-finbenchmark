from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routers import cases
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
    app.include_router(cases.router, prefix="/api")

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_case_detail_and_snapshot_patch():
    client = build_test_client()
    response = client.post(
        "/api/cases/bootstrap",
        json={
            "run_id": "bootstrap-test-001",
            "ticker": "0700.HK",
            "market": "HK",
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "input_narrative": "请分析腾讯的多空博弈。",
            "agent_snapshots": [],
            "resolution_snapshot": None,
        },
    )
    assert response.status_code == 200
    case_id = response.json()["case_id"]

    detail = client.get(f"/api/cases/{case_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["input_narrative"] == "请分析腾讯的多空博弈。"
    assert body["agent_snapshots"] == []
    assert body["resolution_snapshot"] is None

    patch = client.patch(
        f"/api/cases/{case_id}/snapshots",
        json={
            "agent_snapshots": [
                {
                    "agent_id": "traditional_institution",
                    "bias": "bullish",
                    "action_summary": "机构偏向继续加仓",
                    "key_drivers": ["盈利改善"],
                    "observations": ["资金回流"],
                    "confidence": 0.78,
                    "action_horizon": "short_term",
                }
            ],
            "resolution_snapshot": {"marketForceSummary": {"netBias": "bullish"}},
        },
    )
    assert patch.status_code == 200
    patch_body = patch.json()
    assert patch_body["status"] == "updated"
    assert patch_body["agent_count"] == 1
    assert patch_body["has_resolution"] is True

    detail = client.get(f"/api/cases/{case_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["agent_count"] == 1
    assert body["agent_snapshots"][0]["agent_id"] == "traditional_institution"
    assert body["resolution_snapshot"]["marketForceSummary"]["netBias"] == "bullish"
