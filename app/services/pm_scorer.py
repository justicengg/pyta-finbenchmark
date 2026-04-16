"""
Primary-market scoring orchestration.

Phase 3 dimensions (implemented here):
  - reasoning_quality  — LLM judge evaluates report quality
  - internal_consistency — auto-computed from rule-engine issue counts

Future dimensions (stubs only):
  - assumption_calibration — needs GT accumulation
  - outcome_accuracy — needs long-term GT
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import PmEvalCase, PmIssue
from app.models.pm_score import PmEvalScore
from app.services import llm_judge

logger = logging.getLogger(__name__)
_pm_judge_unavailable_logged = False

# Penalty weights for internal_consistency scoring
SEVERITY_PENALTY: dict[str, float] = {
    "critical": 0.3,
    "high": 0.2,
    "medium": 0.1,
    "low": 0.05,
}


def score_case(case: PmEvalCase, db: Session) -> list[PmEvalScore]:
    """
    Compute and persist all available PM scores for a case.
    Returns the list of PmEvalScore records created.
    """
    scores: list[PmEvalScore] = []
    scores.extend(_score_internal_consistency(case, db))
    scores.extend(_score_reasoning_quality(case, db))
    return scores


# ── Internal Consistency ──────────────────────────────────────────────────────


def compute_consistency_score(issues: list[PmIssue]) -> tuple[float, dict]:
    """
    Pure function: compute internal_consistency score from a list of issues.

    score = max(0.0, 1.0 - sum_of_weighted_penalties)

    Returns (score, details_dict).
    """
    penalty = 0.0
    severity_counts: dict[str, int] = {}
    for issue in issues:
        sev = issue.severity
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
        penalty += SEVERITY_PENALTY.get(sev, 0.05)

    score = round(max(0.0, 1.0 - penalty), 4)
    details = {
        "total_issues": len(issues),
        "severity_counts": severity_counts,
        "total_penalty": round(penalty, 4),
    }
    return score, details


def _score_internal_consistency(case: PmEvalCase, db: Session) -> list[PmEvalScore]:
    issues = db.query(PmIssue).filter(PmIssue.case_id == case.id).all()

    score_val, details = compute_consistency_score(issues)

    record = PmEvalScore(
        case_id=case.id,
        dimension="internal_consistency",
        score=score_val,
        scorer_type="auto",
        score_details=details,
        scored_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()
    return [record]


# ── Reasoning Quality ─────────────────────────────────────────────────────────


def _score_reasoning_quality(case: PmEvalCase, db: Session) -> list[PmEvalScore]:
    global _pm_judge_unavailable_logged

    snapshot = case.report_snapshot or {}

    try:
        result = llm_judge.score_pm_reasoning(
            company_name=case.company_name,
            sector=case.sector,
            decision=case.decision,
            confidence=case.confidence,
            report_snapshot=snapshot,
        )
    except llm_judge.LLMJudgeUnavailable as exc:
        if not _pm_judge_unavailable_logged:
            logger.warning("Skipping PM reasoning_quality scoring: %s", exc)
            _pm_judge_unavailable_logged = True
        return []
    except Exception as exc:
        logger.error("PM LLM judge failed for case %s: %s", case.id, exc)
        return []

    record = PmEvalScore(
        case_id=case.id,
        dimension="reasoning_quality",
        score=result["score"],
        scorer_type="llm_judge",
        scorer_model=result.get("model"),
        score_details=result,
        scored_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()
    return [record]
