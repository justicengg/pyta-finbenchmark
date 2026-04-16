"""init eval tables

Revision ID: 20260401_0001
Revises:
Create Date: 2026-04-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260401_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "eval_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(128), nullable=False),
        sa.Column("ticker", sa.String(32), nullable=False),
        sa.Column("market", sa.String(16), nullable=False),
        sa.Column("run_timestamp", sa.DateTime, nullable=False),
        sa.Column("input_narrative", sa.Text, nullable=False),
        sa.Column("agent_snapshots", sa.JSON, nullable=False),
        sa.Column("resolution_snapshot", sa.JSON, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("source", sa.String(32), nullable=False, server_default="online"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_eval_cases_run_id", "eval_cases", ["run_id"])

    op.create_table(
        "eval_ground_truths",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), nullable=False),
        sa.Column("ground_truth_type", sa.String(32), nullable=False),
        sa.Column("horizon_days", sa.Integer, nullable=True),
        sa.Column("data_source", sa.String(32), nullable=False),
        sa.Column("collected_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("value", sa.JSON, nullable=False),
        sa.Column("is_verified", sa.Boolean, server_default="0"),
        sa.Column("needs_review", sa.Boolean, server_default="0"),
    )
    op.create_index("ix_eval_ground_truths_case_id", "eval_ground_truths", ["case_id"])

    op.create_table(
        "eval_scores",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), nullable=False),
        sa.Column("agent_id", sa.String(64), nullable=True),
        sa.Column("dimension", sa.String(32), nullable=False),
        sa.Column("horizon_days", sa.Integer, nullable=True),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("weighted_score", sa.Float, nullable=True),
        sa.Column("scorer_type", sa.String(16), nullable=False),
        sa.Column("scorer_model", sa.String(64), nullable=True),
        sa.Column("score_details", sa.JSON, nullable=False),
        sa.Column("scored_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_eval_scores_case_id", "eval_scores", ["case_id"])


def downgrade() -> None:
    op.drop_table("eval_scores")
    op.drop_table("eval_ground_truths")
    op.drop_table("eval_cases")
