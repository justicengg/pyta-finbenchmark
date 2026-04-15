"""add pm_issues table

Revision ID: 20260415_0003
Revises: 20260415_0002
Create Date: 2026-04-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260415_0003"
down_revision: Union[str, None] = "20260415_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pm_issues",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), nullable=False),
        sa.Column("issue_type", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("dimension", sa.String(64), nullable=True),
        sa.Column("expected", sa.Text, nullable=False),
        sa.Column("actual", sa.Text, nullable=False),
        sa.Column("evidence", sa.JSON, nullable=False),
        sa.Column("root_cause_hint", sa.Text, nullable=True),
        sa.Column("action_suggestion", sa.Text, nullable=True),
        sa.Column("attribution_hint", sa.String(32), nullable=True),
        sa.Column("detected_at", sa.DateTime, nullable=False),
        sa.Column("detected_by", sa.String(32), nullable=False),
    )
    op.create_index("ix_pm_issues_case_id", "pm_issues", ["case_id"])
    op.create_index("ix_pm_issues_issue_type", "pm_issues", ["issue_type"])
    op.create_index("ix_pm_issues_severity", "pm_issues", ["severity"])


def downgrade() -> None:
    op.drop_table("pm_issues")
