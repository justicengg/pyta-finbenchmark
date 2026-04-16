import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PmEvalScore(Base):
    __tablename__ = "pm_eval_scores"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    case_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    # reasoning_quality | internal_consistency | assumption_calibration | outcome_accuracy
    dimension: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    # llm_judge | auto | manual
    scorer_type: Mapped[str] = mapped_column(String(16), nullable=False)
    scorer_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    score_details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
