"""
PmIssue query endpoints — primary-market issue detection results.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PmIssue

router = APIRouter(prefix="/issues", tags=["pm-issues"])


@router.get("/")
def list_issues(
    case_id: str | None = None,
    issue_type: str | None = None,
    severity: str | None = None,
    stage: str | None = None,
    dimension: str | None = None,
    detected_by: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(PmIssue)
    if case_id:
        q = q.filter(PmIssue.case_id == case_id)
    if issue_type:
        q = q.filter(PmIssue.issue_type == issue_type)
    if severity:
        q = q.filter(PmIssue.severity == severity)
    if stage:
        q = q.filter(PmIssue.stage == stage)
    if dimension:
        q = q.filter(PmIssue.dimension == dimension)
    if detected_by:
        q = q.filter(PmIssue.detected_by == detected_by)
    total = q.count()
    items = q.order_by(PmIssue.detected_at.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "items": [_serialize(i) for i in items],
    }


@router.get("/summary")
def issues_summary(db: Session = Depends(get_db)):
    # issue_type × severity cross count
    type_severity = (
        db.query(PmIssue.issue_type, PmIssue.severity, func.count(PmIssue.id))
        .group_by(PmIssue.issue_type, PmIssue.severity)
        .all()
    )
    type_severity_map: dict[str, dict[str, int]] = {}
    for itype, sev, cnt in type_severity:
        type_severity_map.setdefault(itype, {})[sev] = cnt

    # top dimensions
    top_dimensions = (
        db.query(PmIssue.dimension, func.count(PmIssue.id).label("cnt"))
        .filter(PmIssue.dimension.isnot(None))
        .group_by(PmIssue.dimension)
        .order_by(func.count(PmIssue.id).desc())
        .limit(10)
        .all()
    )

    # attribution distribution
    attribution = (
        db.query(PmIssue.attribution_hint, func.count(PmIssue.id))
        .filter(PmIssue.attribution_hint.isnot(None))
        .group_by(PmIssue.attribution_hint)
        .all()
    )

    return {
        "type_severity": type_severity_map,
        "top_dimensions": [{"dimension": d, "count": c} for d, c in top_dimensions],
        "attribution_distribution": {a: c for a, c in attribution},
    }


@router.get("/{issue_id}")
def get_issue(issue_id: str, db: Session = Depends(get_db)):
    issue = db.query(PmIssue).filter(PmIssue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return _serialize(issue)


def _serialize(issue: PmIssue) -> dict:
    return {
        "id": str(issue.id),
        "case_id": str(issue.case_id),
        "issue_type": issue.issue_type,
        "severity": issue.severity,
        "stage": issue.stage,
        "dimension": issue.dimension,
        "expected": issue.expected,
        "actual": issue.actual,
        "evidence": issue.evidence,
        "root_cause_hint": issue.root_cause_hint,
        "action_suggestion": issue.action_suggestion,
        "attribution_hint": issue.attribution_hint,
        "detected_at": issue.detected_at.isoformat() if issue.detected_at else None,
        "detected_by": issue.detected_by,
    }
