"""
Webhook endpoint: receives sandbox run completion events from the main backend.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import EvalCase

router = APIRouter(prefix="/webhook", tags=["webhook"])


class AgentSnapshot(BaseModel):
    agent_id: str
    bias: str  # bullish | bearish | neutral
    action_summary: str = ""
    key_drivers: list[str] = []
    observations: list[str] = []
    confidence: float = 0.0
    action_horizon: str = ""


class SandboxRunCompletedPayload(BaseModel):
    event: str  # "sandbox_run_completed"
    run_id: str
    ticker: str
    market: str
    run_timestamp: datetime
    input_narrative: str
    agent_snapshots: list[AgentSnapshot]
    resolution_snapshot: dict | None = None


@router.post("/sandbox-run-completed")
def receive_sandbox_run(
    payload: SandboxRunCompletedPayload,
    x_webhook_secret: str = Header(default=""),
    db: Session = Depends(get_db),
):
    if (
        settings.main_backend_webhook_secret
        and x_webhook_secret != settings.main_backend_webhook_secret
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    if payload.event != "sandbox_run_completed":
        raise HTTPException(
            status_code=400, detail=f"Unknown event type: {payload.event}"
        )

    # Idempotency: skip if run_id already exists
    existing = db.query(EvalCase).filter(EvalCase.run_id == payload.run_id).first()
    if existing:
        return {"status": "already_exists", "case_id": str(existing.id)}

    case = EvalCase(
        run_id=payload.run_id,
        ticker=payload.ticker,
        market=payload.market,
        run_timestamp=payload.run_timestamp,
        input_narrative=payload.input_narrative,
        agent_snapshots=[s.model_dump() for s in payload.agent_snapshots],
        resolution_snapshot=payload.resolution_snapshot,
        status="pending",
        source="online",
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    return {"status": "created", "case_id": str(case.id)}
