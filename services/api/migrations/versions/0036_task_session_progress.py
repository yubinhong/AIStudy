"""Persist the next exercise position for resumable task sessions.

Revision ID: 0036_task_session_progress
Revises: 0035_chinese_poem_skill
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0036_task_session_progress"
down_revision: str | None = "0035_chinese_poem_skill"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "study_sessions",
        sa.Column("next_exercise_index", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_study_sessions_next_exercise_index_nonnegative",
        "study_sessions",
        "next_exercise_index >= 0",
    )
    op.alter_column("study_sessions", "next_exercise_index", server_default=None)


def downgrade() -> None:
    op.drop_constraint(
        "ck_study_sessions_next_exercise_index_nonnegative",
        "study_sessions",
        type_="check",
    )
    op.drop_column("study_sessions", "next_exercise_index")
