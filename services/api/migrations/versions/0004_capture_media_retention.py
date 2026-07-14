"""Add bounded Capture retention and deletion state.

Revision ID: 0004_capture_media_retention
Revises: 0003_capture_object_upload_state
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_capture_media_retention"
down_revision: str | None = "0003_capture_object_upload_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "captures",
        sa.Column(
            "retention_class",
            sa.String(length=32),
            nullable=False,
            server_default="original",
        ),
    )
    op.add_column("captures", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "captures",
        sa.Column(
            "deletion_status",
            sa.String(length=32),
            nullable=False,
            server_default="active",
        ),
    )
    op.add_column(
        "captures",
        sa.Column("parent_saved", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_captures_expiry_cleanup",
        "captures",
        ["expires_at", "deletion_status", "parent_saved"],
    )


def downgrade() -> None:
    op.drop_index("ix_captures_expiry_cleanup", table_name="captures")
    op.drop_column("captures", "parent_saved")
    op.drop_column("captures", "deletion_status")
    op.drop_column("captures", "expires_at")
    op.drop_column("captures", "retention_class")
