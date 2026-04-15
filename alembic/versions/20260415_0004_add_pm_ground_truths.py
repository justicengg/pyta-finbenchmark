"""add pm_ground_truths table

Revision ID: 20260415_0004
Revises: 20260415_0003
Create Date: 2026-04-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260415_0004"
down_revision: Union[str, None] = "20260415_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pm_ground_truths",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), nullable=False),
        sa.Column("ground_truth_type", sa.String(32), nullable=False),
        sa.Column("assumption_ref", sa.Text, nullable=True),
        sa.Column("data_source", sa.String(32), nullable=False),
        sa.Column("event_date", sa.Date, nullable=True),
        sa.Column("collected_at", sa.DateTime, nullable=False),
        sa.Column("value", sa.JSON, nullable=False),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("needs_review", sa.Boolean, nullable=False, server_default="0"),
    )
    op.create_index("ix_pm_ground_truths_case_id", "pm_ground_truths", ["case_id"])


def downgrade() -> None:
    op.drop_table("pm_ground_truths")
