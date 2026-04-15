import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PmGroundTruth(Base):
    __tablename__ = "pm_ground_truths"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    case_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    ground_truth_type: Mapped[str] = mapped_column(String(32), nullable=False)
    assumption_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_source: Mapped[str] = mapped_column(String(32), nullable=False)
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
