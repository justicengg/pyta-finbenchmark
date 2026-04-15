"""add pm_eval_scores table

Revision ID: 20260415_0005
Revises: 20260415_0004
Create Date: 2026-04-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260415_0005"
down_revision: Union[str, None] = "20260415_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pm_eval_scores",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), nullable=False),
        sa.Column("dimension", sa.String(32), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("scorer_type", sa.String(16), nullable=False),
        sa.Column("scorer_model", sa.String(64), nullable=True),
        sa.Column("score_details", sa.JSON, nullable=False),
        sa.Column("scored_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_pm_eval_scores_case_id", "pm_eval_scores", ["case_id"])


def downgrade() -> None:
    op.drop_table("pm_eval_scores")
