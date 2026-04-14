"""
EvalCase CRUD + bootstrap case creation.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import EvalCase

router = APIRouter(prefix="/cases", tags=["cases"])


class BootstrapCaseRequest(BaseModel):
    """Manually create a historical (bootstrap) eval case."""

    run_id: str
    ticker: str
    market: str
    run_timestamp: datetime
    input_narrative: str
    agent_snapshots: list[dict]
    resolution_snapshot: dict | None = None


class SnapshotUpdateRequest(BaseModel):
    """Patch payload for bootstrap replay snapshot backfill."""

    agent_snapshots: list[dict]
    resolution_snapshot: dict | None = None


@router.post("/bootstrap")
def create_bootstrap_case(body: BootstrapCaseRequest, db: Session = Depends(get_db)):
    existing = db.query(EvalCase).filter(EvalCase.run_id == body.run_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="run_id already exists")

    case = EvalCase(
        run_id=body.run_id,
        ticker=body.ticker,
        market=body.market,
        run_timestamp=body.run_timestamp,
        input_narrative=body.input_narrative,
        agent_snapshots=body.agent_snapshots,
        resolution_snapshot=body.resolution_snapshot,
        status="pending",
        source="bootstrap",
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return {"case_id": str(case.id)}


@router.get("/")
def list_cases(
    status: str | None = None,
    source: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(EvalCase)
    if status:
        q = q.filter(EvalCase.status == status)
    if source:
        q = q.filter(EvalCase.source == source)
    total = q.count()
    cases = q.order_by(EvalCase.run_timestamp.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "items": [_serialize(c) for c in cases],
    }


@router.get("/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db)):
    case = db.query(EvalCase).filter(EvalCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return _serialize(case, detail=True)


@router.patch("/{case_id}/snapshots")
def update_snapshots(
    case_id: str, body: SnapshotUpdateRequest, db: Session = Depends(get_db)
):
    case = db.query(EvalCase).filter(EvalCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    case.agent_snapshots = body.agent_snapshots
    if body.resolution_snapshot is not None:
        case.resolution_snapshot = body.resolution_snapshot
    db.commit()
    db.refresh(case)
    return {
        "status": "updated",
        "case_id": str(case.id),
        "agent_count": len(case.agent_snapshots or []),
        "has_resolution": case.resolution_snapshot is not None,
    }


def _serialize(case: EvalCase, detail: bool = False) -> dict:
    data = {
        "id": str(case.id),
        "run_id": case.run_id,
        "ticker": case.ticker,
        "market": case.market,
        "run_timestamp": case.run_timestamp.isoformat(),
        "status": case.status,
        "source": case.source,
        "agent_count": len(case.agent_snapshots or []),
        "has_resolution": case.resolution_snapshot is not None,
        "created_at": case.created_at.isoformat(),
    }
    if detail:
        data.update(
            {
                "input_narrative": case.input_narrative,
                "agent_snapshots": case.agent_snapshots or [],
                "resolution_snapshot": case.resolution_snapshot,
            }
        )
    return data
