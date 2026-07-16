"""Add the provider-neutral, receipt-only ImageAnalysis job ledger.

Revision ID: 0008_image_analysis_job
Revises: 0007_ocr_job_mode
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_image_analysis_job"
down_revision: str | None = "0007_ocr_job_mode"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "image_analysis_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("capture_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sanitization_schema_version", sa.String(length=64), nullable=False),
        sa.Column("sanitized_derivative_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("extraction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.CheckConstraint("attempt >= 0", name="ck_image_analysis_jobs_attempt_nonnegative"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'blocked')",
            name="ck_image_analysis_jobs_status_allowed",
        ),
        sa.ForeignKeyConstraint(["capture_id"], ["captures.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "household_id",
            "capture_id",
            "idempotency_key",
            name="uq_image_analysis_jobs_capture_idempotency",
        ),
    )
    op.create_index(
        "ix_image_analysis_jobs_capture",
        "image_analysis_jobs",
        ["household_id", "capture_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_image_analysis_jobs_capture", table_name="image_analysis_jobs")
    op.drop_table("image_analysis_jobs")
