"""Persist normalized OCR candidates and their manual-confirmation gate.

Revision ID: 0005_ocr_result_persistence
Revises: 0004_capture_media_retention
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_ocr_result_persistence"
down_revision: str | None = "0004_capture_media_retention"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ocr_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("capture_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("model_version", sa.String(length=80), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requires_manual_confirmation", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_ocr_results_confidence"),
        sa.CheckConstraint(
            "requires_manual_confirmation = true",
            name="ck_ocr_results_manual_confirmation",
        ),
        sa.ForeignKeyConstraint(["capture_id"], ["captures.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_ocr_results_household_child",
        "ocr_results",
        ["household_id", "child_id", "created_at"],
    )
    op.create_table(
        "ocr_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(length=1000), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.CheckConstraint("sequence >= 1", name="ck_ocr_candidates_sequence_positive"),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_ocr_candidates_confidence"
        ),
        sa.ForeignKeyConstraint(["result_id"], ["ocr_results.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("result_id", "sequence", name="uq_ocr_candidates_result_sequence"),
    )


def downgrade() -> None:
    op.drop_table("ocr_candidates")
    op.drop_index("ix_ocr_results_household_child", table_name="ocr_results")
    op.drop_table("ocr_results")
