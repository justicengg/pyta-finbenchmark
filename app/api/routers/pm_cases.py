"""
PmEvalCase CRUD + bootstrap case creation — primary-market version.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PmEvalCase, PmIssue

router = APIRouter(prefix="/cases", tags=["pm-cases"])


class PmBootstrapRequest(BaseModel):
    sandbox_id: str
    company_name: str
    sector: str | None = None
    generated_at: datetime
    decision: str
    confidence: float
    report_snapshot: dict


@router.get("/")
def list_cases(
    status: str | None = None,
    source: str | None = None,
    decision: str | None = None,
    company_name: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(PmEvalCase)
    if status:
        q = q.filter(PmEvalCase.status == status)
    if source:
        q = q.filter(PmEvalCase.source == source)
    if decision:
        q = q.filter(PmEvalCase.decision == decision)
    if company_name:
        q = q.filter(PmEvalCase.company_name.contains(company_name))
    total = q.count()
    cases = (
        q.order_by(PmEvalCase.run_timestamp.desc()).offset(offset).limit(limit).all()
    )
    return {
        "total": total,
        "items": [_serialize(c) for c in cases],
    }


@router.get("/bootstrap", include_in_schema=False)
def bootstrap_placeholder():
    raise HTTPException(status_code=405, detail="Use POST method")


@router.post("/bootstrap")
def create_bootstrap_case(body: PmBootstrapRequest, db: Session = Depends(get_db)):
    existing = (
        db.query(PmEvalCase).filter(PmEvalCase.sandbox_id == body.sandbox_id).first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="sandbox_id already exists")

    case = PmEvalCase(
        sandbox_id=body.sandbox_id,
        company_name=body.company_name,
        sector=body.sector,
        run_timestamp=body.generated_at,
        decision=body.decision,
        confidence=body.confidence,
        report_snapshot=body.report_snapshot,
        status="pending",
        source="bootstrap",
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return {"case_id": str(case.id)}


@router.get("/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db)):
    case = db.query(PmEvalCase).filter(PmEvalCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    issues = db.query(PmIssue).filter(PmIssue.case_id == case_id).all()
    data = _serialize(case, detail=True)
    data["issues"] = [_serialize_issue(i) for i in issues]
    return data


def _serialize(case: PmEvalCase, detail: bool = False) -> dict:
    data = {
        "id": str(case.id),
        "sandbox_id": case.sandbox_id,
        "company_name": case.company_name,
        "sector": case.sector,
        "decision": case.decision,
        "confidence": case.confidence,
        "status": case.status,
        "source": case.source,
        "run_timestamp": case.run_timestamp.isoformat() if case.run_timestamp else None,
        "created_at": case.created_at.isoformat() if case.created_at else None,
    }
    if detail:
        data["report_snapshot"] = case.report_snapshot
    return data


def _serialize_issue(issue: PmIssue) -> dict:
    return {
        "id": str(issue.id),
        "issue_type": issue.issue_type,
        "severity": issue.severity,
        "stage": issue.stage,
        "dimension": issue.dimension,
        "expected": issue.expected,
        "actual": issue.actual,
        "detected_by": issue.detected_by,
    }
