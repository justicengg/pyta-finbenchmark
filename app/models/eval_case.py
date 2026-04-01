import uuid
from datetime import datetime

from sqlalchemy import DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class EvalCase(Base):
    __tablename__ = "eval_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    market: Mapped[str] = mapped_column(String(16), nullable=False)
    run_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    input_narrative: Mapped[str] = mapped_column(Text, nullable=False)
    agent_snapshots: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    resolution_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # pending → collecting → complete
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    # bootstrap | online
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="online")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
