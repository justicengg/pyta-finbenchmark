import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class GroundTruth(Base):
    __tablename__ = "eval_ground_truths"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    # price_direction | event_occurrence | event_impact
    ground_truth_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # 1/2/3/5/10/30/60 for price_direction; null for event types
    horizon_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # akshare | tushare | yfinance | manual
    data_source: Mapped[str] = mapped_column(String(32), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
