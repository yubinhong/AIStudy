"""Add explicit learning-session completion facts.

Revision ID: 0014_session_completion
Revises: 0013_tutor_turn_persistence
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_session_completion"
down_revision: str | None = "0013_tutor_turn_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "study_sessions",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "study_sessions",
        sa.Column("outcome", sa.String(length=32), nullable=True),
    )
    op.create_check_constraint(
        "ck_study_sessions_completion",
        "study_sessions",
        "(status = 'active' AND completed_at IS NULL AND outcome IS NULL) OR "
        "(status = 'completed' AND completed_at IS NOT NULL AND "
        "outcome IN ('learned', 'needs_review', 'skipped'))",
    )
    op.create_index(
        "ix_study_sessions_household_completed",
        "study_sessions",
        ["household_id", "child_id", "completed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_study_sessions_household_completed", table_name="study_sessions")
    op.drop_constraint("ck_study_sessions_completion", "study_sessions", type_="check")
    op.drop_column("study_sessions", "outcome")
    op.drop_column("study_sessions", "completed_at")
