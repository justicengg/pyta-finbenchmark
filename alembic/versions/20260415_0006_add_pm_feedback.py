"""add pm_feedback table

Revision ID: 20260415_0006
Revises: 20260415_0005
Create Date: 2026-04-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260415_0006"
down_revision: Union[str, None] = "20260415_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pm_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), nullable=False),
        sa.Column("issue_id", sa.String(36), nullable=True),
        sa.Column("feedback_type", sa.String(32), nullable=False),
        sa.Column("target_component", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("priority", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("feedback_version", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("resolved_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_pm_feedback_case_id", "pm_feedback", ["case_id"])


def downgrade() -> None:
    op.drop_table("pm_feedback")
