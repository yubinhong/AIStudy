"""Persist human-confirmed question facts for Tutor input.

Revision ID: 0010_verified_question
Revises: 0009_question_extraction
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_verified_question"
down_revision: str | None = "0009_question_extraction"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "verified_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("capture_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("extraction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=32), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=False),
        sa.Column("formulas", postgresql.JSONB(), nullable=False),
        sa.Column("has_diagram", sa.Boolean(), nullable=False),
        sa.Column("has_handwriting", sa.Boolean(), nullable=False),
        sa.Column("answer_text", sa.String(length=1000), nullable=True),
        sa.Column("verified_by", sa.String(length=16), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["extraction_id"], ["question_extractions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["capture_id"], ["captures.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("extraction_id", name="uq_verified_questions_extraction"),
        sa.CheckConstraint("version >= 1", name="ck_verified_questions_version"),
        sa.CheckConstraint("subject = 'math'", name="ck_verified_questions_subject"),
        sa.CheckConstraint(
            "verified_by IN ('child', 'parent')", name="ck_verified_questions_actor"
        ),
    )
    op.create_index(
        "ix_verified_questions_household_capture",
        "verified_questions",
        ["household_id", "capture_id", "verified_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_verified_questions_household_capture", table_name="verified_questions")
    op.drop_table("verified_questions")
