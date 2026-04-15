"""Tests for PM feedback generator + API endpoints."""

import uuid
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routers import pm_feedback
from app.db import Base, get_db
from app.models import PmEvalCase, PmIssue
from app.models.pm_feedback import PmFeedback
from app.services.pm_feedback_generator import generate_feedback_for_issues


def build_test_app():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(pm_feedback.router, prefix="/api/pm")

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), TestingSessionLocal


def _build_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal


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


def _seed_issue(
    db_session, case_id, rule_id="RE-006", severity="critical", evidence=None
):
    if evidence is None:
        evidence = {
            "rule_id": rule_id,
            "confidence": 0.92,
            "high_count": 3,
            "high_dims": ["a", "b", "c"],
        }
    issue = PmIssue(
        id=str(uuid.uuid4()),
        case_id=case_id,
        issue_type="reasoning_error",
        severity=severity,
        stage="verdict",
        dimension="market_validity",
        expected="expected",
        actual="actual",
        evidence=evidence,
        detected_at=datetime.now(timezone.utc),
        detected_by="rule_engine",
    )
    db_session.add(issue)
    db_session.commit()
    db_session.refresh(issue)
    return issue


# ── Generator: per-rule template tests ───────────────────────────


def test_generate_re001():
    Session = _build_db()
    with Session() as db:
        case = _seed_case(db)
        issue = _seed_issue(
            db,
            case.id,
            rule_id="RE-001",
            severity="medium",
            evidence={
                "rule_id": "RE-001",
                "mismatched_assumptions": [{"description": "a"}, {"description": "b"}],
            },
        )
        feedbacks = generate_feedback_for_issues(case.id, [issue], db)
        db.commit()
        assert len(feedbacks) == 1
        fb = feedbacks[0]
        assert fb.feedback_type == "prompt"
        assert fb.target_component == "primary_prompts.ASSUMPTION_SYSTEM_PROMPT"
        assert fb.priority == "p1"
        assert "2 个假设" in fb.description


def test_generate_re002():
    Session = _build_db()
    with Session() as db:
        case = _seed_case(db)
        issue = _seed_issue(
            db,
            case.id,
            rule_id="RE-002",
            severity="high",
            evidence={
                "rule_id": "RE-002",
                "market_validity_score": "high",
                "competition_score": "low",
            },
        )
        feedbacks = generate_feedback_for_issues(case.id, [issue], db)
        db.commit()
        assert len(feedbacks) == 1
        assert feedbacks[0].feedback_type == "orchestrator"
        assert "MACRO_TIMING_MISMATCH" in feedbacks[0].description


def test_generate_re003():
    Session = _build_db()
    with Session() as db:
        case = _seed_case(db)
        issue = _seed_issue(
            db,
            case.id,
            rule_id="RE-003",
            severity="high",
            evidence={
                "rule_id": "RE-003",
                "benchmark_confidence_delta": -0.12,
                "decision": "invest",
            },
        )
        feedbacks = generate_feedback_for_issues(case.id, [issue], db)
        db.commit()
        assert len(feedbacks) == 1
        assert feedbacks[0].priority == "p0"
        assert "-0.12" in feedbacks[0].description
        assert "invest" in feedbacks[0].description


def test_generate_re004():
    Session = _build_db()
    with Session() as db:
        case = _seed_case(db)
        issue = _seed_issue(
            db,
            case.id,
            rule_id="RE-004",
            severity="medium",
            evidence={
                "rule_id": "RE-004",
                "trigger_count": 1,
                "decision": "invest",
            },
        )
        feedbacks = generate_feedback_for_issues(case.id, [issue], db)
        db.commit()
        assert len(feedbacks) == 1
        assert feedbacks[0].feedback_type == "prompt"
        assert "1 个 monitoring triggers" in feedbacks[0].description


def test_generate_re005():
    Session = _build_db()
    with Session() as db:
        case = _seed_case(db)
        issue = _seed_issue(
            db,
            case.id,
            rule_id="RE-005",
            severity="high",
            evidence={
                "rule_id": "RE-005",
                "oscillations": [
                    {
                        "dimension": "team_execution",
                        "round_a": 1,
                        "score_a": "high",
                        "round_b": 2,
                        "score_b": "low",
                    }
                ],
            },
        )
        feedbacks = generate_feedback_for_issues(case.id, [issue], db)
        db.commit()
        assert len(feedbacks) == 1
        assert "team_execution" in feedbacks[0].description
        assert "round 1→2" in feedbacks[0].description


def test_generate_re006():
    Session = _build_db()
    with Session() as db:
        case = _seed_case(db)
        issue = _seed_issue(db, case.id, rule_id="RE-006")
        feedbacks = generate_feedback_for_issues(case.id, [issue], db)
        db.commit()
        assert len(feedbacks) == 1
        assert feedbacks[0].priority == "p0"
        assert "0.92" in feedbacks[0].description
        assert "3 个 HIGH" in feedbacks[0].description


def test_generate_re007():
    Session = _build_db()
    with Session() as db:
        case = _seed_case(db)
        issue = _seed_issue(
            db,
            case.id,
            rule_id="RE-007",
            severity="high",
            evidence={
                "rule_id": "RE-007",
                "unverified_fork_count": 4,
                "decision": "invest",
                "confidence": 0.88,
            },
        )
        feedbacks = generate_feedback_for_issues(case.id, [issue], db)
        db.commit()
        assert len(feedbacks) == 1
        assert "4 个未验证硬假设" in feedbacks[0].description
        assert "invest" in feedbacks[0].description


# ── Generator: dedup + version ───────────────────────────────────


def test_dedup_same_case_and_issue():
    Session = _build_db()
    with Session() as db:
        case = _seed_case(db)
        issue = _seed_issue(db, case.id, rule_id="RE-006")

        first = generate_feedback_for_issues(case.id, [issue], db)
        db.commit()
        assert len(first) == 1

        second = generate_feedback_for_issues(case.id, [issue], db)
        db.commit()
        assert len(second) == 0

        total = db.query(PmFeedback).filter(PmFeedback.case_id == case.id).count()
        assert total == 1


def test_version_increments():
    Session = _build_db()
    with Session() as db:
        case1 = _seed_case(db, sandbox_id="sb-001")
        issue1 = _seed_issue(db, case1.id, rule_id="RE-006")
        fb1 = generate_feedback_for_issues(case1.id, [issue1], db)
        db.commit()
        assert fb1[0].feedback_version == 1

        case2 = _seed_case(db, sandbox_id="sb-002")
        issue2 = _seed_issue(
            db,
            case2.id,
            rule_id="RE-007",
            evidence={
                "rule_id": "RE-007",
                "unverified_fork_count": 3,
                "decision": "invest",
                "confidence": 0.9,
            },
        )
        fb2 = generate_feedback_for_issues(case2.id, [issue2], db)
        db.commit()
        assert fb2[0].feedback_version == 2


def test_multiple_issues_same_version():
    Session = _build_db()
    with Session() as db:
        case = _seed_case(db)
        issue1 = _seed_issue(db, case.id, rule_id="RE-006")
        issue2 = _seed_issue(
            db,
            case.id,
            rule_id="RE-007",
            severity="high",
            evidence={
                "rule_id": "RE-007",
                "unverified_fork_count": 4,
                "decision": "invest",
                "confidence": 0.88,
            },
        )
        feedbacks = generate_feedback_for_issues(case.id, [issue1, issue2], db)
        db.commit()
        assert len(feedbacks) == 2
        assert feedbacks[0].feedback_version == feedbacks[1].feedback_version


def test_unknown_rule_id_skipped():
    Session = _build_db()
    with Session() as db:
        case = _seed_case(db)
        issue = _seed_issue(
            db,
            case.id,
            rule_id="RE-999",
            evidence={"rule_id": "RE-999"},
        )
        feedbacks = generate_feedback_for_issues(case.id, [issue], db)
        db.commit()
    assert len(feedbacks) == 0


# ── API: GET list + filters ──────────────────────────────────────


def test_api_list_empty():
    client, _ = build_test_app()
    resp = client.get("/api/pm/feedback/")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_api_list_with_filters():
    client, Session = build_test_app()
    with Session() as db:
        case = _seed_case(db)
        issue1 = _seed_issue(db, case.id, rule_id="RE-006")
        issue2 = _seed_issue(
            db,
            case.id,
            rule_id="RE-001",
            severity="medium",
            evidence={
                "rule_id": "RE-001",
                "mismatched_assumptions": [{"description": "a"}],
            },
        )
        generate_feedback_for_issues(case.id, [issue1, issue2], db)
        db.commit()

    # Filter by feedback_type=prompt → RE-001 only
    resp = client.get("/api/pm/feedback/?feedback_type=prompt")
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["feedback_type"] == "prompt"

    # Filter by priority=p0 → RE-006 only
    resp2 = client.get("/api/pm/feedback/?priority=p0")
    assert resp2.json()["total"] == 1

    # Filter by status=open → all
    resp3 = client.get("/api/pm/feedback/?status=open")
    assert resp3.json()["total"] == 2


# ── API: PATCH status ────────────────────────────────────────────


def test_api_patch_status():
    client, Session = build_test_app()
    with Session() as db:
        case = _seed_case(db)
        issue = _seed_issue(db, case.id, rule_id="RE-006")
        feedbacks = generate_feedback_for_issues(case.id, [issue], db)
        db.commit()
        fb_id = str(feedbacks[0].id)

    resp = client.patch(f"/api/pm/feedback/{fb_id}", json={"status": "acknowledged"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "acknowledged"
    assert resp.json()["resolved_at"] is None


def test_api_patch_resolved_sets_timestamp():
    client, Session = build_test_app()
    with Session() as db:
        case = _seed_case(db)
        issue = _seed_issue(db, case.id, rule_id="RE-006")
        feedbacks = generate_feedback_for_issues(case.id, [issue], db)
        db.commit()
        fb_id = str(feedbacks[0].id)

    resp = client.patch(f"/api/pm/feedback/{fb_id}", json={"status": "resolved"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"
    assert resp.json()["resolved_at"] is not None


def test_api_patch_not_found():
    client, _ = build_test_app()
    resp = client.patch("/api/pm/feedback/nonexistent", json={"status": "resolved"})
    assert resp.status_code == 404


# ── API: summary ─────────────────────────────────────────────────


def test_api_summary():
    client, Session = build_test_app()
    with Session() as db:
        case = _seed_case(db)
        i1 = _seed_issue(db, case.id, rule_id="RE-006")
        i2 = _seed_issue(
            db,
            case.id,
            rule_id="RE-007",
            evidence={
                "rule_id": "RE-007",
                "unverified_fork_count": 3,
                "decision": "invest",
                "confidence": 0.9,
            },
        )
        i3 = _seed_issue(
            db,
            case.id,
            rule_id="RE-001",
            severity="medium",
            evidence={
                "rule_id": "RE-001",
                "mismatched_assumptions": [{"description": "a"}],
            },
        )
        generate_feedback_for_issues(case.id, [i1, i2, i3], db)
        db.commit()

    resp = client.get("/api/pm/feedback/summary")
    assert resp.status_code == 200
    data = resp.json()
    # RE-006 and RE-007 both target _resolve_decision → orchestrator should have it
    assert "orchestrator" in data
    assert "prompt" in data


# ── API: agent-heatmap ───────────────────────────────────────────


def test_api_heatmap():
    client, Session = build_test_app()
    with Session() as db:
        case = _seed_case(db)
        # RE-006 issue has dimension="market_validity"
        issue = _seed_issue(db, case.id, rule_id="RE-006")
        generate_feedback_for_issues(case.id, [issue], db)
        db.commit()

    resp = client.get("/api/pm/feedback/agent-heatmap")
    assert resp.status_code == 200
    data = resp.json()
    assert "market_validity" in data
    assert "orchestrator" in data["market_validity"]


# ── E2E: detect issues → generate feedback → query ──────────────


def test_e2e_flow():
    client, Session = build_test_app()
    with Session() as db:
        case = _seed_case(db)
        # Simulate detection: RE-006 + RE-003
        i1 = _seed_issue(db, case.id, rule_id="RE-006")
        i2 = _seed_issue(
            db,
            case.id,
            rule_id="RE-003",
            severity="high",
            evidence={
                "rule_id": "RE-003",
                "benchmark_confidence_delta": -0.08,
                "decision": "invest",
            },
        )
        generate_feedback_for_issues(case.id, [i1, i2], db)
        db.commit()
        case_id = str(case.id)

    # List all
    resp = client.get(f"/api/pm/feedback/?case_id={case_id}")
    assert resp.json()["total"] == 2

    items = resp.json()["items"]
    priorities = {i["priority"] for i in items}
    assert priorities == {"p0"}  # both RE-006 and RE-003 are p0

    # Resolve one
    fb_id = items[0]["id"]
    client.patch(f"/api/pm/feedback/{fb_id}", json={"status": "resolved"})

    # Filter open only
    resp2 = client.get(f"/api/pm/feedback/?case_id={case_id}&status=open")
    assert resp2.json()["total"] == 1
