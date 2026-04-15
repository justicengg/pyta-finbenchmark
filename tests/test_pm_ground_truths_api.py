"""Tests for PM ground-truths API (POST / GET / PATCH)."""

import uuid
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routers import pm_ground_truths
from app.db import Base, get_db
from app.models import PmEvalCase, PmGroundTruth


def build_test_app():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(pm_ground_truths.router, prefix="/api/pm")

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), TestingSessionLocal


def _seed_case(db_session, sandbox_id="sb-001"):
    case = PmEvalCase(
        id=str(uuid.uuid4()),
        sandbox_id=sandbox_id,
        company_name="TestCo",
        sector="AI",
        run_timestamp=datetime.now(timezone.utc),
        decision="invest",
        confidence=0.9,
        report_snapshot={"decision": "invest"},
        status="detected",
        source="online",
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    return case


def _seed_gt(db_session, case_id, gt_type="assumption_violated", is_verified=False):
    gt = PmGroundTruth(
        id=str(uuid.uuid4()),
        case_id=case_id,
        ground_truth_type=gt_type,
        assumption_ref="毛利率维持50%以上",
        data_source="manual",
        event_date=None,
        collected_at=datetime.now(timezone.utc),
        value={
            "assumption_description": "毛利率维持50%以上",
            "evidence": "Q3 财报显示毛利率降至38%",
        },
        is_verified=is_verified,
        needs_review=False,
    )
    db_session.add(gt)
    db_session.commit()
    db_session.refresh(gt)
    return gt


# ── POST /api/pm/ground-truths ──────────────────────────────────


def test_create_ground_truth():
    client, Session = build_test_app()
    with Session() as db:
        case = _seed_case(db)

    resp = client.post(
        "/api/pm/ground-truths/",
        json={
            "case_id": case.id,
            "ground_truth_type": "assumption_violated",
            "assumption_ref": "毛利率维持50%以上",
            "data_source": "manual",
            "event_date": "2026-03-15",
            "value": {
                "assumption_description": "毛利率维持50%以上",
                "evidence": "Q3 财报显示毛利率降至38%",
                "source_url": "https://example.com",
            },
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data


def test_create_funding_event():
    client, Session = build_test_app()
    with Session() as db:
        case = _seed_case(db)

    resp = client.post(
        "/api/pm/ground-truths/",
        json={
            "case_id": case.id,
            "ground_truth_type": "funding_event",
            "value": {
                "round_name": "Series D",
                "amount_usd": 500_000_000,
                "lead_investors": ["Sequoia"],
                "valuation": 15_000_000_000,
            },
        },
    )
    assert resp.status_code == 200


def test_create_invalid_type_returns_422():
    client, Session = build_test_app()
    with Session() as db:
        case = _seed_case(db)

    resp = client.post(
        "/api/pm/ground-truths/",
        json={
            "case_id": case.id,
            "ground_truth_type": "invalid_type",
            "value": {},
        },
    )
    assert resp.status_code == 422


def test_create_invalid_data_source_returns_422():
    client, Session = build_test_app()
    with Session() as db:
        case = _seed_case(db)

    resp = client.post(
        "/api/pm/ground-truths/",
        json={
            "case_id": case.id,
            "ground_truth_type": "news_signal",
            "data_source": "unknown_source",
            "value": {"headline": "test"},
        },
    )
    assert resp.status_code == 422


# ── GET /api/pm/ground-truths ───────────────────────────────────


def test_list_ground_truths_empty():
    client, _ = build_test_app()
    resp = client.get("/api/pm/ground-truths/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_list_filter_by_case_id():
    client, Session = build_test_app()
    with Session() as db:
        case1 = _seed_case(db, sandbox_id="sb-001")
        case2 = _seed_case(db, sandbox_id="sb-002")
        case1_id = str(case1.id)
        _seed_gt(db, case1_id)
        _seed_gt(db, case1_id)
        _seed_gt(db, case2.id)

    resp = client.get(f"/api/pm/ground-truths/?case_id={case1_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


def test_list_filter_by_type():
    client, Session = build_test_app()
    with Session() as db:
        case = _seed_case(db)
        _seed_gt(db, case.id, gt_type="assumption_violated")
        _seed_gt(db, case.id, gt_type="funding_event")

    resp = client.get("/api/pm/ground-truths/?ground_truth_type=funding_event")
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["ground_truth_type"] == "funding_event"


def test_list_filter_by_is_verified():
    client, Session = build_test_app()
    with Session() as db:
        case = _seed_case(db)
        _seed_gt(db, case.id, is_verified=True)
        _seed_gt(db, case.id, is_verified=False)

    resp = client.get("/api/pm/ground-truths/?is_verified=true")
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["is_verified"] is True


def test_list_pagination():
    client, Session = build_test_app()
    with Session() as db:
        case = _seed_case(db)
        for _ in range(5):
            _seed_gt(db, case.id)

    resp = client.get("/api/pm/ground-truths/?limit=2&offset=0")
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2

    resp2 = client.get("/api/pm/ground-truths/?limit=2&offset=2")
    data2 = resp2.json()
    assert len(data2["items"]) == 2


# ── PATCH /api/pm/ground-truths/{id} ────────────────────────────


def test_patch_mark_verified():
    client, Session = build_test_app()
    with Session() as db:
        case = _seed_case(db)
        gt = _seed_gt(db, case.id, is_verified=False)

    resp = client.patch(
        f"/api/pm/ground-truths/{gt.id}",
        json={"is_verified": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_verified"] is True


def test_patch_update_value():
    client, Session = build_test_app()
    with Session() as db:
        case = _seed_case(db)
        gt = _seed_gt(db, case.id)

    new_value = {"assumption_description": "更新后", "evidence": "新证据"}
    resp = client.patch(
        f"/api/pm/ground-truths/{gt.id}",
        json={"value": new_value},
    )
    assert resp.status_code == 200
    assert resp.json()["value"] == new_value


def test_patch_not_found():
    client, _ = build_test_app()
    resp = client.patch(
        "/api/pm/ground-truths/nonexistent-id",
        json={"is_verified": True},
    )
    assert resp.status_code == 404


# ── End-to-end: POST → GET → PATCH → GET ────────────────────────


def test_e2e_create_query_verify():
    client, Session = build_test_app()
    with Session() as db:
        case = _seed_case(db)

    # 1. POST
    create_resp = client.post(
        "/api/pm/ground-truths/",
        json={
            "case_id": case.id,
            "ground_truth_type": "assumption_violated",
            "assumption_ref": "毛利率维持50%以上",
            "value": {
                "assumption_description": "毛利率维持50%以上",
                "evidence": "Q3 财报显示毛利率降至38%",
            },
        },
    )
    assert create_resp.status_code == 200
    gt_id = create_resp.json()["id"]

    # 2. GET — confirm it appears
    list_resp = client.get(f"/api/pm/ground-truths/?case_id={case.id}")
    assert list_resp.json()["total"] == 1
    item = list_resp.json()["items"][0]
    assert item["id"] == gt_id
    assert item["is_verified"] is False
    assert item["assumption_ref"] == "毛利率维持50%以上"

    # 3. PATCH — mark verified
    patch_resp = client.patch(
        f"/api/pm/ground-truths/{gt_id}",
        json={"is_verified": True},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["is_verified"] is True

    # 4. GET — confirm updated
    list_resp2 = client.get(
        f"/api/pm/ground-truths/?case_id={case.id}&is_verified=true"
    )
    assert list_resp2.json()["total"] == 1
