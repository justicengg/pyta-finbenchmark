"""
Cron job: trigger scoring for cases that just became complete.
"""

from __future__ import annotations

import logging

from app.db import SessionLocal
from app.models import EvalCase
from app.services import scorer

logger = logging.getLogger(__name__)


def run() -> None:
    db = SessionLocal()
    try:
        # Find complete cases not yet scored (no scores exist)
        from app.models import EvalScore
        from sqlalchemy import exists

        cases = (
            db.query(EvalCase)
            .filter(
                EvalCase.status == "complete",
                ~exists().where(EvalScore.case_id == EvalCase.id),
            )
            .all()
        )
        logger.info("run_scoring: %d cases to score", len(cases))

        for case in cases:
            try:
                scorer.score_case(case, db)
                logger.info("Scored case %s", case.id)
            except Exception as exc:
                logger.error("Failed to score case %s: %s", case.id, exc)
    finally:
        db.close()
