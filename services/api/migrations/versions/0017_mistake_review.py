"""Persist verified-question mistakes and deterministic review schedules.

Revision ID: 0017_mistake_review
Revises: 0016_child_account_uniqueness
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_mistake_review"
down_revision: str | None = "0016_child_account_uniqueness"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mistake_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verified_question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["verified_question_id"], ["verified_questions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["session_id"], ["study_sessions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "household_id",
            "child_id",
            "verified_question_id",
            name="uq_mistake_records_question",
        ),
        sa.CheckConstraint("status IN ('open', 'resolved')", name="ck_mistake_records_status"),
    )
    op.create_index(
        "ix_mistake_records_household_child_status",
        "mistake_records",
        ["household_id", "child_id", "status", "created_at"],
    )
    op.create_table(
        "review_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mistake_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("repetitions", sa.Integer(), nullable=False),
        sa.Column("last_outcome", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mistake_id"], ["mistake_records.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("mistake_id", name="uq_review_schedules_mistake"),
        sa.CheckConstraint("interval_days >= 1", name="ck_review_schedules_interval"),
        sa.CheckConstraint("repetitions >= 0", name="ck_review_schedules_repetitions"),
        sa.CheckConstraint(
            "last_outcome IS NULL OR last_outcome IN ('correct', 'needs_review', 'skipped')",
            name="ck_review_schedules_outcome",
        ),
    )
    op.create_index(
        "ix_review_schedules_due",
        "review_schedules",
        ["household_id", "child_id", "due_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_review_schedules_due", table_name="review_schedules")
    op.drop_table("review_schedules")
    op.drop_index("ix_mistake_records_household_child_status", table_name="mistake_records")
    op.drop_table("mistake_records")
