import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PmFeedback(Base):
    __tablename__ = "pm_feedback"
    __table_args__ = (
        UniqueConstraint("case_id", "issue_id", name="uq_pm_feedback_case_issue"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    case_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    issue_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # prompt | orchestrator | dataset
    feedback_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_component: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # p0 | p1 | p2
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    # open | acknowledged | resolved | wont_fix
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    feedback_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
