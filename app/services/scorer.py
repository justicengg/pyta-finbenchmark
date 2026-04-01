"""
Scoring orchestration: computes all dimensions for a completed EvalCase.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import EvalCase, EvalScore, GroundTruth
from app.services import llm_judge

logger = logging.getLogger(__name__)

# Gradient weights: reward early accuracy (T+10 = 1.0 baseline)
GRADIENT_WEIGHTS: dict[int, float] = {
    1: 2.0,
    2: 1.8,
    3: 1.6,
    5: 1.4,
    10: 1.0,
    30: 0.7,
    60: 0.5,
}

# Bias → price direction mapping
BIAS_TO_DIRECTION: dict[str, str] = {
    "bullish": "up",
    "bearish": "down",
    "neutral": "flat",
}


def score_case(case: EvalCase, db: Session) -> None:
    """
    Compute and persist all available scores for a case.
    Called after ground truth is collected.
    """
    ground_truths = (
        db.query(GroundTruth).filter(GroundTruth.case_id == case.id).all()
    )

    price_gts = {
        gt.horizon_days: gt
        for gt in ground_truths
        if gt.ground_truth_type == "price_direction"
    }

    _score_direction_accuracy(case, price_gts, db)
    _score_resolution_accuracy(case, price_gts, db)
    _score_reasoning_quality(case, db)
    _score_event_alignment(case, ground_truths, db)


# ── Direction Accuracy ─────────────────────────────────────────────────────────

def _score_direction_accuracy(
    case: EvalCase,
    price_gts: dict[int, GroundTruth],
    db: Session,
) -> None:
    agents: list[dict] = case.agent_snapshots or []

    for agent in agents:
        agent_id = agent.get("agent_id", "unknown")
        predicted_direction = BIAS_TO_DIRECTION.get(agent.get("bias", ""), "flat")

        for horizon_days, gt in price_gts.items():
            actual_direction = gt.value.get("direction", "")
            score = _direction_score(predicted_direction, actual_direction, gt.value.get("change_pct", 0))
            weight = GRADIENT_WEIGHTS.get(horizon_days, 1.0)

            db.add(EvalScore(
                case_id=case.id,
                agent_id=agent_id,
                dimension="direction_accuracy",
                horizon_days=horizon_days,
                score=score,
                weighted_score=round(score * weight, 4),
                scorer_type="auto",
                score_details={
                    "predicted": predicted_direction,
                    "actual": actual_direction,
                    "change_pct": gt.value.get("change_pct"),
                    "gradient_weight": weight,
                },
                scored_at=datetime.utcnow(),
            ))

    db.commit()


def _direction_score(predicted: str, actual: str, change_pct: float) -> float:
    if predicted == actual:
        return 1.0
    # Partial credit: neutral vs. small move (±0.5–1.5%)
    if predicted == "flat" and abs(change_pct) <= 1.5:
        return 0.5
    return 0.0


# ── Resolution Accuracy ────────────────────────────────────────────────────────

def _score_resolution_accuracy(
    case: EvalCase,
    price_gts: dict[int, GroundTruth],
    db: Session,
) -> None:
    resolution = case.resolution_snapshot
    if not resolution:
        return

    net_bias = resolution.get("marketForceSummary", {}).get("netBias", "")
    predicted_direction = {"bullish": "up", "bearish": "down"}.get(net_bias, "flat")

    # Use T+5 and T+10 as the primary verification horizons for resolution
    for horizon_days in (5, 10):
        gt = price_gts.get(horizon_days)
        if not gt:
            continue
        actual_direction = gt.value.get("direction", "")
        score = _direction_score(predicted_direction, actual_direction, gt.value.get("change_pct", 0))

        db.add(EvalScore(
            case_id=case.id,
            agent_id=None,
            dimension="resolution_accuracy",
            horizon_days=horizon_days,
            score=score,
            weighted_score=None,
            scorer_type="auto",
            score_details={
                "net_bias": net_bias,
                "predicted": predicted_direction,
                "actual": actual_direction,
                "regime": resolution.get("marketForceSummary", {}).get("regime"),
            },
            scored_at=datetime.utcnow(),
        ))

    db.commit()


# ── Reasoning Quality ──────────────────────────────────────────────────────────

def _score_reasoning_quality(case: EvalCase, db: Session) -> None:
    agents: list[dict] = case.agent_snapshots or []

    for agent in agents:
        agent_id = agent.get("agent_id", "unknown")
        try:
            result = llm_judge.score_reasoning(
                ticker=case.ticker,
                market=case.market,
                input_narrative=case.input_narrative,
                agent_snapshot=agent,
            )
            db.add(EvalScore(
                case_id=case.id,
                agent_id=agent_id,
                dimension="reasoning_quality",
                horizon_days=None,
                score=result["score"],
                weighted_score=None,
                scorer_type="llm_judge",
                scorer_model=result.get("model"),
                score_details=result,
                scored_at=datetime.utcnow(),
            ))
        except Exception as exc:
            logger.error("LLM judge failed for agent %s in case %s: %s", agent_id, case.id, exc)

    db.commit()


# ── Event Alignment ────────────────────────────────────────────────────────────

def _score_event_alignment(
    case: EvalCase,
    ground_truths: list[GroundTruth],
    db: Session,
) -> None:
    event_gts = [gt for gt in ground_truths if gt.ground_truth_type == "event_impact"]
    if not event_gts:
        return

    correct = sum(
        1 for gt in event_gts
        if gt.value.get("predicted_direction") == gt.value.get("actual_direction")
    )
    score = correct / len(event_gts)

    db.add(EvalScore(
        case_id=case.id,
        agent_id=None,
        dimension="event_alignment",
        horizon_days=None,
        score=round(score, 4),
        weighted_score=None,
        scorer_type="auto",
        score_details={
            "total_events": len(event_gts),
            "correct": correct,
        },
        scored_at=datetime.utcnow(),
    ))
    db.commit()
