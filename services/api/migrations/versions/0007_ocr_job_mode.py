"""Persist the requested local OCR mode for each queued job.

Revision ID: 0007_ocr_job_mode
Revises: 0006_ocr_job_ledger
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_ocr_job_mode"
down_revision: str | None = "0006_ocr_job_ledger"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ocr_jobs",
        sa.Column("mode", sa.String(length=16), nullable=False, server_default="text"),
    )
    op.create_check_constraint(
        "ck_ocr_jobs_mode_allowed",
        "ocr_jobs",
        "mode IN ('text', 'formula')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_ocr_jobs_mode_allowed", "ocr_jobs", type_="check")
    op.drop_column("ocr_jobs", "mode")
