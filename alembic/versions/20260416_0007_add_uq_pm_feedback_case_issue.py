"""add unique constraint on pm_feedback (case_id, issue_id)

Revision ID: 20260416_0007
Revises: 20260415_0006
Create Date: 2026-04-16

"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260416_0007"
down_revision: Union[str, None] = "20260415_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("pm_feedback") as batch_op:
        batch_op.create_unique_constraint(
            "uq_pm_feedback_case_issue", ["case_id", "issue_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("pm_feedback") as batch_op:
        batch_op.drop_constraint("uq_pm_feedback_case_issue", type_="unique")
