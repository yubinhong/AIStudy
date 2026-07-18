"""Persist Tutor hint turns as child-owned append-only learning facts.

Revision ID: 0013_tutor_turn_persistence
Revises: 0012_profile_persistence
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_tutor_turn_persistence"
down_revision: str | None = "0012_profile_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tutor_turns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verified_question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("prompt", sa.String(length=500), nullable=False),
        sa.Column("next_step", sa.String(length=500), nullable=False),
        sa.Column("cost_cents", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["verified_question_id"], ["verified_questions.id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint("level BETWEEN 1 AND 3", name="ck_tutor_turns_level"),
        sa.CheckConstraint("cost_cents >= 0", name="ck_tutor_turns_cost"),
    )
    op.create_index(
        "ix_tutor_turns_household_child_created",
        "tutor_turns",
        ["household_id", "child_id", "created_at", "id"],
    )
    op.create_index(
        "ix_tutor_turns_verified_question",
        "tutor_turns",
        ["verified_question_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_tutor_turns_verified_question", table_name="tutor_turns")
    op.drop_index("ix_tutor_turns_household_child_created", table_name="tutor_turns")
    op.drop_table("tutor_turns")
