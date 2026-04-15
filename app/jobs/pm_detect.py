"""
Catch-up job: re-run rule engine for pending cases that have no issues.
Handles edge cases where webhook-time detection failed.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import exists

from app.db import SessionLocal
from app.models import PmEvalCase, PmIssue
from app.services.pm_rule_engine import detect_reasoning_errors

logger = logging.getLogger(__name__)


def run() -> None:
    db = SessionLocal()
    try:
        # Find pending cases with no associated issues
        cases = (
            db.query(PmEvalCase)
            .filter(
                PmEvalCase.status == "pending",
                ~exists().where(PmIssue.case_id == PmEvalCase.id),
            )
            .all()
        )
        logger.info("pm_detect: processing %d pending cases", len(cases))

        for case in cases:
            _detect_case(case, db)

    finally:
        db.close()


def _detect_case(case: PmEvalCase, db) -> None:
    snapshot = case.report_snapshot
    if not snapshot:
        logger.warning("case %s has no report_snapshot, skipping", case.id)
        return

    issues = detect_reasoning_errors(snapshot)
    now = datetime.now(timezone.utc)

    for issue_dict in issues:
        issue = PmIssue(
            case_id=case.id,
            detected_at=now,
            **issue_dict,
        )
        db.add(issue)

    case.status = "detected"
    db.commit()
    logger.info("case %s: detected %d issues, status → detected", case.id, len(issues))
