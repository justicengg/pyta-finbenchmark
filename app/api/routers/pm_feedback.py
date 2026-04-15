"""
PmFeedback endpoints — query and manage feedback generated from PM issues.
"""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.pm_feedback import PmFeedback
from app.models.pm_issue import PmIssue

router = APIRouter(prefix="/feedback", tags=["pm-feedback"])

VALID_STATUSES = {"open", "acknowledged", "resolved", "wont_fix"}


class PatchFeedbackRequest(BaseModel):
    status: Literal["open", "acknowledged", "resolved", "wont_fix"] | None = None


# ── List ─────────────────────────────────────────────────────────


@router.get("/")
def list_feedback(
    feedback_type: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    target_component: str | None = None,
    case_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(PmFeedback)
    if feedback_type:
        q = q.filter(PmFeedback.feedback_type == feedback_type)
    if status:
        q = q.filter(PmFeedback.status == status)
    if priority:
        q = q.filter(PmFeedback.priority == priority)
    if target_component:
        q = q.filter(PmFeedback.target_component == target_component)
    if case_id:
        q = q.filter(PmFeedback.case_id == case_id)
    total = q.count()
    items = q.order_by(PmFeedback.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "items": [_serialize(fb) for fb in items],
    }


# ── Summary ──────────────────────────────────────────────────────


@router.get("/summary")
def feedback_summary(db: Session = Depends(get_db)):
    rows = (
        db.query(
            PmFeedback.feedback_type,
            PmFeedback.target_component,
            func.count(PmFeedback.id),
        )
        .group_by(PmFeedback.feedback_type, PmFeedback.target_component)
        .all()
    )
    result: dict[str, dict[str, int]] = {}
    for ftype, component, cnt in rows:
        result.setdefault(ftype, {})[component] = cnt
    return result


# ── Agent Heatmap ────────────────────────────────────────────────


@router.get("/agent-heatmap")
def agent_heatmap(db: Session = Depends(get_db)):
    rows = (
        db.query(
            PmIssue.dimension,
            PmFeedback.feedback_type,
            func.count(PmFeedback.id),
        )
        .join(PmIssue, PmFeedback.issue_id == PmIssue.id)
        .filter(PmIssue.dimension.isnot(None))
        .group_by(PmIssue.dimension, PmFeedback.feedback_type)
        .all()
    )
    result: dict[str, dict[str, int]] = {}
    for dim, ftype, cnt in rows:
        result.setdefault(dim, {})[ftype] = cnt
    return result


# ── Patch ────────────────────────────────────────────────────────


@router.patch("/{feedback_id}")
def patch_feedback(
    feedback_id: str,
    body: PatchFeedbackRequest,
    db: Session = Depends(get_db),
):
    fb = db.query(PmFeedback).filter(PmFeedback.id == feedback_id).first()
    if not fb:
        raise HTTPException(status_code=404, detail="Feedback not found")
    if body.status is not None:
        fb.status = body.status
        if body.status == "resolved":
            fb.resolved_at = datetime.now(timezone.utc)
        else:
            fb.resolved_at = None
    db.commit()
    db.refresh(fb)
    return _serialize(fb)


# ── Serializer ───────────────────────────────────────────────────


def _serialize(fb: PmFeedback) -> dict:
    return {
        "id": str(fb.id),
        "case_id": str(fb.case_id),
        "issue_id": str(fb.issue_id) if fb.issue_id else None,
        "feedback_type": fb.feedback_type,
        "target_component": fb.target_component,
        "description": fb.description,
        "priority": fb.priority,
        "status": fb.status,
        "feedback_version": fb.feedback_version,
        "created_at": fb.created_at.isoformat() if fb.created_at else None,
        "resolved_at": fb.resolved_at.isoformat() if fb.resolved_at else None,
    }
