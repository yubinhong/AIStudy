"""Create Capture metadata and append-only manual corrections.

Revision ID: 0002_capture_manual_correction
Revises: 0001_learning_event_foundation
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_capture_manual_correction"
down_revision: str | None = "0001_learning_event_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "captures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("media_type", sa.String(length=32), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("byte_size > 0 AND byte_size <= 8000000", name="ck_captures_byte_size"),
        sa.CheckConstraint("version >= 1", name="ck_captures_version_positive"),
        sa.ForeignKeyConstraint(["session_id"], ["study_sessions.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_captures_household_session", "captures", ["household_id", "session_id"])
    op.create_table(
        "capture_corrections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("capture_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("corrected_text", sa.String(length=1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("sequence >= 1", name="ck_capture_corrections_sequence_positive"),
        sa.ForeignKeyConstraint(["capture_id"], ["captures.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("capture_id", "sequence", name="uq_capture_corrections_sequence"),
    )
    op.create_index(
        "ix_capture_corrections_household_capture",
        "capture_corrections",
        ["household_id", "capture_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_capture_corrections_household_capture", table_name="capture_corrections")
    op.drop_table("capture_corrections")
    op.drop_index("ix_captures_household_session", table_name="captures")
    op.drop_table("captures")
