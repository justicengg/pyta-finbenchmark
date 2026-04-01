import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class EvalScore(Base):
    __tablename__ = "eval_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # direction_accuracy | reasoning_quality | resolution_accuracy | event_alignment
    dimension: Mapped[str] = mapped_column(String(32), nullable=False)
    horizon_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    weighted_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # llm_judge | human | auto
    scorer_type: Mapped[str] = mapped_column(String(16), nullable=False)
    scorer_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    score_details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    scored_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
