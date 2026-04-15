"""Tests for PM issues API, cases API, and detect job."""

import uuid
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routers import pm_cases, pm_issues
from app.db import Base, get_db
from app.models import PmEvalCase, PmIssue


def build_test_app():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(pm_cases.router, prefix="/api/pm")
    app.include_router(pm_issues.router, prefix="/api/pm")

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), TestingSessionLocal


def _seed_case(db_session, sandbox_id="sb-001", decision="invest", confidence=0.9):
    case = PmEvalCase(
        id=str(uuid.uuid4()),
        sandbox_id=sandbox_id,
        company_name="TestCo",
        sector="AI",
        run_timestamp=datetime.now(timezone.utc),
        decision=decision,
        confidence=confidence,
        report_snapshot={"decision": decision, "confidence": confidence},
        status="detected",
        source="online",
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    return case


def _seed_issue(db_session, case_id, severity="high", issue_type="reasoning_error"):
    issue = PmIssue(
        id=str(uuid.uuid4()),
        case_id=case_id,
        issue_type=issue_type,
        severity=severity,
        stage="verdict",
        dimension="market_validity",
        expected="expected behavior",
        actual="actual behavior",
        evidence={"rule_id": "RE-006"},
        attribution_hint="orchestrator",
        detected_at=datetime.now(timezone.utc),
        detected_by="rule_engine",
    )
    db_session.add(issue)
    db_session.commit()
    db_session.refresh(issue)
    return issue


# ── Cases API ────────────────────────────────────────────────────────────


def test_cases_list_excludes_report_snapshot():
    client, Session = build_test_app()
    db = Session()
    _seed_case(db)
    db.close()

    resp = client.get("/api/pm/cases/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert "report_snapshot" not in item
    assert item["company_name"] == "TestCo"


def test_cases_detail_includes_report_and_issues():
    client, Session = build_test_app()
    db = Session()
    case = _seed_case(db)
    case_id = case.id
    _seed_issue(db, case_id)
    db.close()

    resp = client.get(f"/api/pm/cases/{case_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert "report_snapshot" in body
    assert len(body["issues"]) == 1
    assert body["issues"][0]["severity"] == "high"


def test_cases_filter_by_decision():
    client, Session = build_test_app()
    db = Session()
    _seed_case(db, sandbox_id="sb-a", decision="invest")
    _seed_case(db, sandbox_id="sb-b", decision="pass_for_now")
    db.close()

    resp = client.get("/api/pm/cases/?decision=invest")
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["decision"] == "invest"


def test_cases_bootstrap():
    client, _ = build_test_app()
    resp = client.post(
        "/api/pm/cases/bootstrap",
        json={
            "sandbox_id": "bootstrap-001",
            "company_name": "BootstrapCo",
            "generated_at": "2026-04-15T00:00:00Z",
            "decision": "monitor",
            "confidence": 0.5,
            "report_snapshot": {"test": True},
        },
    )
    assert resp.status_code == 200
    assert "case_id" in resp.json()


def test_cases_bootstrap_invalid_datetime():
    """Invalid generated_at should return 422, not 500."""
    client, _ = build_test_app()
    resp = client.post(
        "/api/pm/cases/bootstrap",
        json={
            "sandbox_id": "bad-ts-001",
            "company_name": "BadTsCo",
            "generated_at": "not-a-date",
            "decision": "monitor",
            "confidence": 0.5,
            "report_snapshot": {"test": True},
        },
    )
    assert resp.status_code == 422


def test_cases_bootstrap_duplicate():
    client, _ = build_test_app()
    payload = {
        "sandbox_id": "dup-001",
        "company_name": "DupCo",
        "generated_at": "2026-04-15T00:00:00Z",
        "decision": "invest",
        "confidence": 0.8,
        "report_snapshot": {},
    }
    resp1 = client.post("/api/pm/cases/bootstrap", json=payload)
    assert resp1.status_code == 200
    resp2 = client.post("/api/pm/cases/bootstrap", json=payload)
    assert resp2.status_code == 409


# ── Issues API ───────────────────────────────────────────────────────────


def test_issues_list_with_filter():
    client, Session = build_test_app()
    db = Session()
    case = _seed_case(db)
    _seed_issue(db, case.id, severity="critical")
    _seed_issue(db, case.id, severity="medium")
    db.close()

    resp = client.get("/api/pm/issues/?severity=critical")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["severity"] == "critical"


def test_issues_detail():
    client, Session = build_test_app()
    db = Session()
    case = _seed_case(db)
    issue = _seed_issue(db, case.id)
    db.close()

    resp = client.get(f"/api/pm/issues/{issue.id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == issue.id


def test_issues_detail_not_found():
    client, _ = build_test_app()
    resp = client.get("/api/pm/issues/nonexistent")
    assert resp.status_code == 404


def test_issues_summary():
    client, Session = build_test_app()
    db = Session()
    case = _seed_case(db)
    _seed_issue(db, case.id, severity="critical", issue_type="reasoning_error")
    _seed_issue(db, case.id, severity="high", issue_type="reasoning_error")
    db.close()

    resp = client.get("/api/pm/issues/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert "type_severity" in body
    assert "reasoning_error" in body["type_severity"]
    assert "top_dimensions" in body
    assert "attribution_distribution" in body


# ── Detect Job ───────────────────────────────────────────────────────────


def test_detect_job_processes_pending_cases():
    """Verify pm_detect.run() picks up pending cases and creates issues."""
    from sqlalchemy import create_engine as ce
    from sqlalchemy.orm import sessionmaker as sm
    from sqlalchemy.pool import StaticPool as sp

    engine = ce("sqlite://", connect_args={"check_same_thread": False}, poolclass=sp)
    TestSession = sm(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    db = TestSession()
    # Create a case that would trigger RE-004 (invest + 0 triggers) and RE-006
    case = PmEvalCase(
        id=str(uuid.uuid4()),
        sandbox_id="detect-test-001",
        company_name="DetectCo",
        run_timestamp=datetime.now(timezone.utc),
        decision="invest",
        confidence=0.95,
        report_snapshot={
            "decision": "invest",
            "confidence": 0.95,
            "monitoring_triggers": [],
            "uncertainty_map": {
                "assessments": {
                    "market_validity": {"score": "high"},
                    "tech_barrier": {"score": "high"},
                }
            },
        },
        status="pending",
        source="online",
    )
    db.add(case)
    db.commit()
    case_id = case.id

    # Monkey-patch SessionLocal to use our test session
    import app.jobs.pm_detect as pm_detect_mod

    original_session_local = pm_detect_mod.SessionLocal
    pm_detect_mod.SessionLocal = TestSession

    try:
        pm_detect_mod.run()
    finally:
        pm_detect_mod.SessionLocal = original_session_local

    # Verify
    db2 = TestSession()
    updated_case = db2.query(PmEvalCase).filter(PmEvalCase.id == case_id).first()
    assert updated_case.status == "detected"

    issues = db2.query(PmIssue).filter(PmIssue.case_id == case_id).all()
    assert len(issues) >= 2  # RE-004 + RE-006 at minimum
    rule_ids = {i.evidence.get("rule_id") for i in issues}
    assert "RE-004" in rule_ids
    assert "RE-006" in rule_ids
    db2.close()


def test_detect_job_empty_snapshot_not_stuck():
    """Empty dict snapshot should be finalized, not stuck pending forever."""
    from sqlalchemy import create_engine as ce
    from sqlalchemy.orm import sessionmaker as sm
    from sqlalchemy.pool import StaticPool as sp

    engine = ce("sqlite://", connect_args={"check_same_thread": False}, poolclass=sp)
    TestSession = sm(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    db = TestSession()
    case = PmEvalCase(
        id=str(uuid.uuid4()),
        sandbox_id="empty-snap-001",
        company_name="EmptyCo",
        run_timestamp=datetime.now(timezone.utc),
        decision="invest",
        confidence=0.5,
        report_snapshot={},
        status="pending",
        source="bootstrap",
    )
    db.add(case)
    db.commit()
    case_id = case.id

    import app.jobs.pm_detect as pm_detect_mod

    original_session_local = pm_detect_mod.SessionLocal
    pm_detect_mod.SessionLocal = TestSession
    try:
        pm_detect_mod.run()
    finally:
        pm_detect_mod.SessionLocal = original_session_local

    db2 = TestSession()
    updated = db2.query(PmEvalCase).filter(PmEvalCase.id == case_id).first()
    assert updated.status == "detected", (
        "Empty snapshot case should be finalized, not stuck pending"
    )
    db2.close()
