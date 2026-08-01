"""Add indexes for bounded learning history reads and cleanup.

Revision ID: 0030_learning_history_retention
Revises: 0029_english_speaking_practice
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0030_learning_history_retention"
down_revision: str | None = "0029_english_speaking_practice"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_verified_questions_household_child_verified",
        "verified_questions",
        ["household_id", "child_id", "verified_at", "id"],
    )
    op.create_index(
        "ix_mistake_records_status_resolved",
        "mistake_records",
        ["status", "resolved_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_mistake_records_status_resolved", table_name="mistake_records")
    op.drop_index(
        "ix_verified_questions_household_child_verified",
        table_name="verified_questions",
    )
