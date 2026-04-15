import uuid
from datetime import datetime

from sqlalchemy import DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PmIssue(Base):
    __tablename__ = "pm_issues"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    case_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    issue_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    dimension: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expected: Mapped[str] = mapped_column(Text, nullable=False)
    actual: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False)
    root_cause_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    attribution_hint: Mapped[str | None] = mapped_column(String(32), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    detected_by: Mapped[str] = mapped_column(String(32), nullable=False)
