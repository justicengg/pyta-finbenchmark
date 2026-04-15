"""
PmGroundTruth endpoints — manual ground truth input for primary-market cases.
"""

from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PmGroundTruth

router = APIRouter(prefix="/ground-truths", tags=["pm-ground-truths"])

VALID_GT_TYPES = {
    "assumption_verified",
    "assumption_violated",
    "funding_event",
    "key_metric_update",
    "news_signal",
}

VALID_DATA_SOURCES = {"manual", "news_scraper", "crunchbase", "pitchbook"}


class CreateGTRequest(BaseModel):
    case_id: str
    ground_truth_type: Literal[
        "assumption_verified",
        "assumption_violated",
        "funding_event",
        "key_metric_update",
        "news_signal",
    ]
    assumption_ref: str | None = None
    data_source: Literal["manual", "news_scraper", "crunchbase", "pitchbook"] = "manual"
    event_date: date | None = None
    value: dict
    is_verified: bool = False
    needs_review: bool = False


class PatchGTRequest(BaseModel):
    is_verified: bool | None = None
    needs_review: bool | None = None
    value: dict | None = None
    assumption_ref: str | None = None
    event_date: date | None = None


@router.post("/")
def create_ground_truth(body: CreateGTRequest, db: Session = Depends(get_db)):
    gt = PmGroundTruth(
        case_id=body.case_id,
        ground_truth_type=body.ground_truth_type,
        assumption_ref=body.assumption_ref,
        data_source=body.data_source,
        event_date=body.event_date,
        collected_at=datetime.now(timezone.utc),
        value=body.value,
        is_verified=body.is_verified,
        needs_review=body.needs_review,
    )
    db.add(gt)
    db.commit()
    db.refresh(gt)
    return {"id": str(gt.id)}


@router.get("/")
def list_ground_truths(
    case_id: str | None = None,
    ground_truth_type: str | None = None,
    is_verified: bool | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(PmGroundTruth)
    if case_id:
        q = q.filter(PmGroundTruth.case_id == case_id)
    if ground_truth_type:
        q = q.filter(PmGroundTruth.ground_truth_type == ground_truth_type)
    if is_verified is not None:
        q = q.filter(PmGroundTruth.is_verified == is_verified)
    total = q.count()
    items = (
        q.order_by(PmGroundTruth.collected_at.desc()).offset(offset).limit(limit).all()
    )
    return {
        "total": total,
        "items": [_serialize(gt) for gt in items],
    }


@router.patch("/{gt_id}")
def patch_ground_truth(gt_id: str, body: PatchGTRequest, db: Session = Depends(get_db)):
    gt = db.query(PmGroundTruth).filter(PmGroundTruth.id == gt_id).first()
    if not gt:
        raise HTTPException(status_code=404, detail="Ground truth not found")
    for field in (
        "is_verified",
        "needs_review",
        "value",
        "assumption_ref",
        "event_date",
    ):
        val = getattr(body, field)
        if val is not None:
            setattr(gt, field, val)
    db.commit()
    db.refresh(gt)
    return _serialize(gt)


def _serialize(gt: PmGroundTruth) -> dict:
    return {
        "id": str(gt.id),
        "case_id": str(gt.case_id),
        "ground_truth_type": gt.ground_truth_type,
        "assumption_ref": gt.assumption_ref,
        "data_source": gt.data_source,
        "event_date": gt.event_date.isoformat() if gt.event_date else None,
        "collected_at": gt.collected_at.isoformat() if gt.collected_at else None,
        "value": gt.value,
        "is_verified": gt.is_verified,
        "needs_review": gt.needs_review,
    }
