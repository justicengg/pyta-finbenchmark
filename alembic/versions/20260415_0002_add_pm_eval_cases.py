"""add pm_eval_cases table

Revision ID: 20260415_0002
Revises: 20260401_0001
Create Date: 2026-04-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260415_0002"
down_revision: Union[str, None] = "20260401_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pm_eval_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sandbox_id", sa.String(128), nullable=False),
        sa.Column("company_name", sa.String(256), nullable=False),
        sa.Column("sector", sa.String(128), nullable=True),
        sa.Column("run_timestamp", sa.DateTime, nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("report_snapshot", sa.JSON, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("source", sa.String(32), nullable=False, server_default="online"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_pm_eval_cases_sandbox_id", "pm_eval_cases", ["sandbox_id"], unique=True
    )
    op.create_index("ix_pm_eval_cases_company_name", "pm_eval_cases", ["company_name"])
    op.create_index("ix_pm_eval_cases_decision", "pm_eval_cases", ["decision"])
    op.create_index("ix_pm_eval_cases_status", "pm_eval_cases", ["status"])


def downgrade() -> None:
    op.drop_table("pm_eval_cases")
