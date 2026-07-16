"""Persist provider-neutral question extraction for manual review.

Revision ID: 0009_question_extraction
Revises: 0008_image_analysis_job
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_question_extraction"
down_revision: str | None = "0008_image_analysis_job"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "question_extractions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("image_analysis_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("capture_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("subject", sa.String(length=32), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=False),
        sa.Column("formulas", postgresql.JSONB(), nullable=False),
        sa.Column("has_diagram", sa.Boolean(), nullable=False),
        sa.Column("has_handwriting", sa.Boolean(), nullable=False),
        sa.Column("detected_answer", sa.String(length=1000), nullable=True),
        sa.Column("question_region_count", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("needs_confirmation", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("question_region_count >= 0", name="ck_question_extractions_regions"),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_question_extractions_confidence"
        ),
        sa.CheckConstraint(
            "needs_confirmation = TRUE", name="ck_question_extractions_confirmation"
        ),
        sa.ForeignKeyConstraint(
            ["image_analysis_job_id"], ["image_analysis_jobs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["capture_id"], ["captures.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("image_analysis_job_id", name="uq_question_extractions_job"),
    )
    op.create_index(
        "ix_question_extractions_capture",
        "question_extractions",
        ["household_id", "capture_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_question_extractions_capture", table_name="question_extractions")
    op.drop_table("question_extractions")
