"""Persist short-lived, idempotent child data export snapshots.

Revision ID: 0015_child_data_export
Revises: 0014_session_completion
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_child_data_export"
down_revision: str | None = "0014_session_completion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "child_data_exports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"], ondelete="CASCADE"),
        sa.CheckConstraint("expires_at > created_at", name="ck_child_data_exports_expiry"),
    )
    op.create_index(
        "ix_child_data_exports_household_child_created",
        "child_data_exports",
        ["household_id", "child_id", "created_at", "id"],
    )
    op.create_index(
        "ix_child_data_exports_expires_at",
        "child_data_exports",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_child_data_exports_expires_at", table_name="child_data_exports")
    op.drop_index(
        "ix_child_data_exports_household_child_created",
        table_name="child_data_exports",
    )
    op.drop_table("child_data_exports")
