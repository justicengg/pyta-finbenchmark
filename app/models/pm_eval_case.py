import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PmEvalCase(Base):
    __tablename__ = "pm_eval_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sandbox_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    sector: Mapped[str | None] = mapped_column(String(128), nullable=True)
    run_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    report_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="online")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
