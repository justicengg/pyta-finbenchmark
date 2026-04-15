"""
Webhook endpoint: receives primary-market run completion events from the main backend.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import PmEvalCase

router = APIRouter(prefix="/webhook", tags=["pm-webhook"])


class PrimaryRunCompletedPayload(BaseModel):
    event: str
    sandbox_id: str
    company_name: str
    sector: str | None = None
    generated_at: datetime
    decision: str
    confidence: float
    decision_rationale: str = ""
    overall_verdict: str = ""
    monitoring_triggers: list[dict] = []
    uncertainty_map: dict = {}
    founder_analysis: dict = {}
    key_assumptions: dict = {}
    financial_lens: dict = {}
    competitive_landscape: dict | None = None
    market_sizing: dict | None = None
    valuation_analysis: dict | None = None
    benchmark_comparison: dict | None = None
    investor_lens_impact: dict | None = None
    reasoning_trace: dict | None = None
    path_forks: list[dict] = []
    context_summary: dict = {}
    active_dimensions: list[str] = []
    restore_integrity: str = "full"
    skipped_dimensions_by_round: dict = {}
    registry_snapshot: dict = {}


@router.post("/primary-run-completed")
def receive_primary_run(
    payload: PrimaryRunCompletedPayload,
    x_webhook_secret: str = Header(default=""),
    db: Session = Depends(get_db),
):
    if (
        settings.main_backend_webhook_secret
        and x_webhook_secret != settings.main_backend_webhook_secret
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    if payload.event != "primary_run_completed":
        raise HTTPException(
            status_code=400, detail=f"Unknown event type: {payload.event}"
        )

    # Idempotency: skip if sandbox_id already exists
    existing = (
        db.query(PmEvalCase).filter(PmEvalCase.sandbox_id == payload.sandbox_id).first()
    )
    if existing:
        return {"status": "already_exists", "case_id": str(existing.id)}

    case = PmEvalCase(
        sandbox_id=payload.sandbox_id,
        company_name=payload.company_name,
        sector=payload.sector,
        run_timestamp=payload.generated_at,
        decision=payload.decision,
        confidence=payload.confidence,
        report_snapshot=payload.model_dump(mode="json"),
        status="pending",
        source="online",
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    return {"status": "created", "case_id": str(case.id)}
