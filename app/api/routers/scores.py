"""
Score query endpoints — used by the dashboard frontend.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import EvalScore
from app.services.scorer import GRADIENT_WEIGHTS

router = APIRouter(prefix="/scores", tags=["scores"])

HORIZONS = [1, 2, 3, 5, 10, 30, 60]


@router.get("/case/{case_id}")
def get_case_scores(case_id: UUID, db: Session = Depends(get_db)):
    scores = db.query(EvalScore).filter(EvalScore.case_id == case_id).all()
    return [_serialize(s) for s in scores]


@router.get("/gradient-curve")
def get_gradient_curve(
    ticker: str | None = None,
    market: str | None = None,
    limit_cases: int = 100,
    db: Session = Depends(get_db),
):
    """
    Returns average DA score per horizon, across recent cases.
    This is the primary optimization signal — shows where accuracy peaks.
    """
    from app.models import EvalCase

    q = (
        db.query(EvalScore)
        .join(EvalCase, EvalScore.case_id == EvalCase.id)
        .filter(EvalScore.dimension == "direction_accuracy")
    )
    if ticker:
        q = q.filter(EvalCase.ticker == ticker)
    if market:
        q = q.filter(EvalCase.market == market)

    rows = (
        q.with_entities(
            EvalScore.horizon_days, func.avg(EvalScore.score).label("avg_score")
        )
        .group_by(EvalScore.horizon_days)
        .all()
    )

    curve = {row.horizon_days: round(float(row.avg_score), 4) for row in rows}
    return {
        "horizons": HORIZONS,
        "avg_da_by_horizon": {str(h): curve.get(h) for h in HORIZONS},
        "gradient_weights": GRADIENT_WEIGHTS,
    }


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    """
    Aggregate summary across all scored cases — for dashboard overview.
    """
    dims = [
        "direction_accuracy",
        "reasoning_quality",
        "resolution_accuracy",
        "event_alignment",
    ]
    result = {}
    for dim in dims:
        row = (
            db.query(func.avg(EvalScore.score), func.count(EvalScore.id))
            .filter(EvalScore.dimension == dim)
            .first()
        )
        avg, count = row
        result[dim] = {
            "avg_score": round(float(avg), 4) if avg else None,
            "sample_count": count,
        }
    return result


def _serialize(score: EvalScore) -> dict:
    return {
        "id": str(score.id),
        "case_id": str(score.case_id),
        "agent_id": score.agent_id,
        "dimension": score.dimension,
        "horizon_days": score.horizon_days,
        "score": score.score,
        "weighted_score": score.weighted_score,
        "scorer_type": score.scorer_type,
        "score_details": score.score_details,
        "scored_at": score.scored_at.isoformat(),
    }
