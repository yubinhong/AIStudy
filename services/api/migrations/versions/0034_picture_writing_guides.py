"""Persist bounded picture-writing observation guidance.

Revision ID: 0034_picture_writing_guides
Revises: 0033_chinese_poem_spot_check
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0034_picture_writing_guides"
down_revision: str | None = "0033_chinese_poem_spot_check"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "picture_writing_guides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("capture_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("guide_json", postgresql.JSONB(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["capture_id"], ["captures.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "household_id",
            "capture_id",
            "child_id",
            "idempotency_key",
            name="uq_picture_writing_guide_idempotency",
        ),
    )
    op.create_index(
        "ix_picture_writing_guides_lookup",
        "picture_writing_guides",
        ["household_id", "child_id", "capture_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_picture_writing_guides_lookup", table_name="picture_writing_guides")
    op.drop_table("picture_writing_guides")
