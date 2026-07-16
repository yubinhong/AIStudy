"""Persist idempotent OCR job state for a recoverable Worker boundary.

Revision ID: 0006_ocr_job_ledger
Revises: 0005_ocr_result_persistence
Create Date: 2026-07-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_ocr_job_ledger"
down_revision: str | None = "0005_ocr_result_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ocr_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("capture_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.CheckConstraint("attempt >= 0", name="ck_ocr_jobs_attempt_nonnegative"),
        sa.ForeignKeyConstraint(["capture_id"], ["captures.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["result_id"], ["ocr_results.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "household_id",
            "capture_id",
            "idempotency_key",
            name="uq_ocr_jobs_capture_idempotency",
        ),
    )
    op.create_index("ix_ocr_jobs_claim", "ocr_jobs", ["status", "enqueued_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_ocr_jobs_claim", table_name="ocr_jobs")
    op.drop_table("ocr_jobs")
