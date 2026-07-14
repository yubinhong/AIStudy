"""Persist internal private-object references for Capture upload confirmation.

Revision ID: 0003_capture_object_upload_state
Revises: 0002_capture_manual_correction
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_capture_object_upload_state"
down_revision: str | None = "0002_capture_manual_correction"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable preserves pre-upload Capture metadata created by 0002.
    op.add_column("captures", sa.Column("object_key", sa.String(length=180), nullable=True))
    op.create_index("uq_captures_object_key", "captures", ["object_key"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_captures_object_key", table_name="captures")
    op.drop_column("captures", "object_key")
