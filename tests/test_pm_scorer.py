"""Tests for PM scorer: internal_consistency (pure + DB) and reasoning_quality."""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import PmEvalCase, PmIssue
from app.models.pm_score import PmEvalScore
from app.services.pm_scorer import compute_consistency_score, score_case


def _build_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal


def _seed_case(db_session, sandbox_id="sb-001", status="detected"):
    case = PmEvalCase(
        id=str(uuid.uuid4()),
        sandbox_id=sandbox_id,
        company_name="Cursor Inc",
        sector="AI",
        run_timestamp=datetime.now(timezone.utc),
        decision="invest",
        confidence=0.85,
        report_snapshot={
            "decision": "invest",
            "confidence": 0.85,
            "key_assumptions": [
                {
                    "description": "毛利率维持50%以上",
                    "type": "hard",
                    "falsifiable": True,
                }
            ],
            "dimension_scores": {
                "market_validity": {"score": 0.8, "uncertainty": 0.2},
                "team_execution": {"score": 0.7, "uncertainty": 0.3},
            },
            "path_forks": [
                {"scenario": "bull", "probability": 0.6, "outcome": "Series D"},
                {"scenario": "bear", "probability": 0.4, "outcome": "down round"},
            ],
            "financial_analysis": {
                "arr": 200_000_000,
                "burn_rate": 5_000_000,
                "runway_months": 18,
            },
            "monitoring_triggers": [{"metric": "arr_growth", "threshold": "< 50% YoY"}],
        },
        status=status,
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
        expected="expected",
        actual="actual",
        evidence={"rule_id": "RE-001"},
        detected_at=datetime.now(timezone.utc),
        detected_by="rule_engine",
    )
    db_session.add(issue)
    db_session.commit()
    return issue


# ── Pure function tests for compute_consistency_score ────────────


def test_consistency_no_issues():
    score, details = compute_consistency_score([])
    assert score == 1.0
    assert details["total_issues"] == 0
    assert details["total_penalty"] == 0.0


def test_consistency_single_critical():
    """One critical issue: penalty=0.3, score=0.7"""
    Session = _build_db()
    with Session() as db:
        case = _seed_case(db)
        _seed_issue(db, case.id, severity="critical")
        issues = db.query(PmIssue).filter(PmIssue.case_id == case.id).all()

    score, details = compute_consistency_score(issues)
    assert score == 0.7
    assert details["severity_counts"] == {"critical": 1}
    assert details["total_penalty"] == 0.3


def test_consistency_mixed_severities():
    """1 critical + 2 high + 1 medium: penalty = 0.3 + 0.4 + 0.1 = 0.8, score = 0.2"""
    Session = _build_db()
    with Session() as db:
        case = _seed_case(db)
        _seed_issue(db, case.id, severity="critical")
        _seed_issue(db, case.id, severity="high")
        _seed_issue(db, case.id, severity="high")
        _seed_issue(db, case.id, severity="medium")
        issues = db.query(PmIssue).filter(PmIssue.case_id == case.id).all()

    score, details = compute_consistency_score(issues)
    assert score == 0.2
    assert details["total_issues"] == 4


def test_consistency_floor_at_zero():
    """Many issues should floor at 0.0, not go negative."""
    Session = _build_db()
    with Session() as db:
        case = _seed_case(db)
        for _ in range(5):
            _seed_issue(db, case.id, severity="critical")
        issues = db.query(PmIssue).filter(PmIssue.case_id == case.id).all()

    score, details = compute_consistency_score(issues)
    assert score == 0.0
    assert details["total_penalty"] == 1.5


def test_consistency_low_severity():
    """2 low issues: penalty = 0.1, score = 0.9"""
    Session = _build_db()
    with Session() as db:
        case = _seed_case(db)
        _seed_issue(db, case.id, severity="low")
        _seed_issue(db, case.id, severity="low")
        issues = db.query(PmIssue).filter(PmIssue.case_id == case.id).all()

    score, details = compute_consistency_score(issues)
    assert score == 0.9
    assert details["severity_counts"] == {"low": 2}


# ── DB integration: _score_internal_consistency via score_case ────


def test_score_case_internal_consistency_persisted():
    """score_case persists internal_consistency to PmEvalScore table."""
    Session = _build_db()
    with Session() as db:
        case = _seed_case(db)
        _seed_issue(db, case.id, severity="high")
        _seed_issue(db, case.id, severity="medium")

        # Mock LLM judge to isolate internal_consistency test
        with patch(
            "app.services.pm_scorer.llm_judge.score_pm_reasoning",
            side_effect=Exception("skip"),
        ):
            scores = score_case(case, db)

        # Should have exactly 1 score (internal_consistency only, reasoning skipped)
        assert len(scores) == 1
        ic_score = scores[0]
        assert ic_score.dimension == "internal_consistency"
        assert ic_score.scorer_type == "auto"
        assert ic_score.score == 0.7  # 1.0 - 0.2 - 0.1
        assert ic_score.score_details["total_issues"] == 2

        # Verify persisted in DB
        db_scores = db.query(PmEvalScore).filter(PmEvalScore.case_id == case.id).all()
        assert len(db_scores) == 1
        assert db_scores[0].dimension == "internal_consistency"


def test_score_case_no_issues_full_consistency():
    """Case with no issues should get perfect internal_consistency score."""
    Session = _build_db()
    with Session() as db:
        case = _seed_case(db)

        with patch(
            "app.services.pm_scorer.llm_judge.score_pm_reasoning",
            side_effect=Exception("skip"),
        ):
            scores = score_case(case, db)

        assert len(scores) == 1
        assert scores[0].score == 1.0


# ── Reasoning quality with mocked LLM judge ─────────────────────


def test_score_case_reasoning_quality_with_mock():
    """When LLM judge returns valid result, reasoning_quality is persisted."""
    mock_result = {
        "assumption_quality": 20,
        "dimension_coverage": 18,
        "financial_depth": 22,
        "risk_identification": 15,
        "total": 75,
        "score": 0.75,
        "rationale": "Good assumptions, weak risk coverage",
        "model": "claude-opus-4-6",
    }

    Session = _build_db()
    with Session() as db:
        case = _seed_case(db)

        with patch(
            "app.services.pm_scorer.llm_judge.score_pm_reasoning",
            return_value=mock_result,
        ):
            scores = score_case(case, db)

        # Should have 2 scores: internal_consistency + reasoning_quality
        assert len(scores) == 2
        dims = {s.dimension for s in scores}
        assert dims == {"internal_consistency", "reasoning_quality"}

        rq = next(s for s in scores if s.dimension == "reasoning_quality")
        assert rq.score == 0.75
        assert rq.scorer_type == "llm_judge"
        assert rq.scorer_model == "claude-opus-4-6"
        assert rq.score_details["assumption_quality"] == 20


def test_score_case_llm_unavailable_graceful():
    """When LLM judge is unavailable, only internal_consistency is scored."""
    from app.services.llm_judge import LLMJudgeUnavailable

    Session = _build_db()
    with Session() as db:
        case = _seed_case(db)

        with patch(
            "app.services.pm_scorer.llm_judge.score_pm_reasoning",
            side_effect=LLMJudgeUnavailable("no API key"),
        ):
            scores = score_case(case, db)

        assert len(scores) == 1
        assert scores[0].dimension == "internal_consistency"
