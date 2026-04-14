"""
Daily cron job: collect ground truth price data for all pending eval cases.
For each case, check which T+N horizons have passed and fetch price data.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from app.db import SessionLocal
from app.models import EvalCase, GroundTruth
from app.services.price_collector import cross_verify

logger = logging.getLogger(__name__)

HORIZONS = [1, 2, 3, 5, 10, 30, 60]


def run() -> None:
    db = SessionLocal()
    try:
        cases = (
            db.query(EvalCase)
            .filter(EvalCase.status.in_(["pending", "collecting"]))
            .all()
        )
        logger.info("collect_gt: processing %d cases", len(cases))

        for case in cases:
            _process_case(case, db)

    finally:
        db.close()


def _process_case(case: EvalCase, db) -> None:
    run_date = case.run_timestamp.date()
    today = date.today()

    collected_horizons = {
        gt.horizon_days
        for gt in db.query(GroundTruth)
        .filter(
            GroundTruth.case_id == case.id,
            GroundTruth.ground_truth_type == "price_direction",
        )
        .all()
    }

    newly_collected = 0
    for horizon in HORIZONS:
        if horizon in collected_horizons:
            continue

        target_date = _next_trading_day(run_date + timedelta(days=horizon))
        if target_date > today:
            continue  # not yet

        result = cross_verify(case.ticker, case.market, target_date)
        if result is None:
            logger.warning(
                "No price data for %s on %s (T+%d)", case.ticker, target_date, horizon
            )
            continue

        gt = GroundTruth(
            case_id=case.id,
            ground_truth_type="price_direction",
            horizon_days=horizon,
            data_source=result.get("source", "unknown"),
            value=result,
            needs_review=result.get("needs_review", False),
        )
        db.add(gt)
        newly_collected += 1

    if newly_collected:
        db.commit()
        logger.info(
            "case %s: collected %d new ground truth records", case.id, newly_collected
        )

    # Update case status
    all_collected = _all_horizons_collected(case, db)
    if all_collected and case.status != "complete":
        case.status = "complete"
        db.commit()
        logger.info("case %s marked complete, ready for scoring", case.id)
    elif newly_collected and case.status == "pending":
        case.status = "collecting"
        db.commit()


def _all_horizons_collected(case: EvalCase, db) -> bool:
    run_date = case.run_timestamp.date()
    today = date.today()
    due_horizons = [
        h for h in HORIZONS if _next_trading_day(run_date + timedelta(days=h)) <= today
    ]
    if not due_horizons:
        return False

    collected = {
        gt.horizon_days
        for gt in db.query(GroundTruth)
        .filter(
            GroundTruth.case_id == case.id,
            GroundTruth.ground_truth_type == "price_direction",
        )
        .all()
    }
    return all(h in collected for h in due_horizons)


def _next_trading_day(d: date) -> date:
    """Skip weekends. Does not account for public holidays (good enough for MVP)."""
    while d.weekday() >= 5:  # 5=Saturday, 6=Sunday
        d += timedelta(days=1)
    return d
