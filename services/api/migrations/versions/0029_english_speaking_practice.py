"""Add provider-neutral English speaking settings and summary sessions.

Revision ID: 0029_english_speaking_practice
Revises: 0028_super_admin_ownership
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0029_english_speaking_practice"
down_revision: str | None = "0028_super_admin_ownership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "english_practice_settings",
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("level", sa.String(16), nullable=False, server_default="pre_a1"),
        sa.Column("consent_version", sa.String(64), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("household_id", "child_id"),
        sa.ForeignKeyConstraint(
            ["child_id", "household_id"],
            ["child_profiles.id", "child_profiles.household_id"],
            ondelete="CASCADE",
            name="fk_english_settings_child_household",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["accounts.id"],
            ondelete="SET NULL",
            name="fk_english_settings_updated_by",
        ),
        sa.CheckConstraint("level IN ('pre_a1', 'a1', 'a2')", name="ck_english_settings_level"),
        sa.CheckConstraint("version >= 0", name="ck_english_settings_version"),
    )
    op.create_table(
        "english_practice_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scenario_id", sa.String(32), nullable=False),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("turn_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_audio_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_audio_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_micros", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "feedback_tags", postgresql.ARRAY(sa.String(64)), nullable=False, server_default="{}"
        ),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(
            ["child_id", "household_id"],
            ["child_profiles.id", "child_profiles.household_id"],
            ondelete="CASCADE",
            name="fk_english_sessions_child_household",
        ),
        sa.CheckConstraint(
            "scenario_id IN ('greetings', 'school', 'food_order')",
            name="ck_english_sessions_scenario",
        ),
        sa.CheckConstraint("level IN ('pre_a1', 'a1', 'a2')", name="ck_english_sessions_level"),
        sa.CheckConstraint(
            "status IN ('active', 'completed', 'interrupted', 'failed')",
            name="ck_english_sessions_status",
        ),
        sa.CheckConstraint(
            "duration_seconds BETWEEN 0 AND 480", name="ck_english_sessions_duration"
        ),
        sa.CheckConstraint(
            "turn_count >= 0 AND input_audio_ms >= 0 AND output_audio_ms >= 0",
            name="ck_english_sessions_metrics",
        ),
        sa.CheckConstraint(
            "cardinality(feedback_tags) <= 3", name="ck_english_sessions_feedback_count"
        ),
    )
    op.create_index(
        "ix_english_sessions_child_started",
        "english_practice_sessions",
        ["household_id", "child_id", "started_at"],
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_english_sessions_one_active_child "
        "ON english_practice_sessions (household_id, child_id) WHERE status = 'active'"
    )
    op.create_table(
        "english_practice_idempotency",
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.String(96), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("household_id", "operation", "idempotency_key"),
    )


def downgrade() -> None:
    connection = op.get_bind()
    session_count = connection.execute(sa.text("SELECT count(*) FROM english_practice_sessions"))
    settings_count = connection.execute(sa.text("SELECT count(*) FROM english_practice_settings"))
    if session_count.scalar_one() or settings_count.scalar_one():
        raise RuntimeError(
            "english practice downgrade requires explicit confirmation and empty English tables"
        )
    op.drop_table("english_practice_idempotency")
    op.drop_index("uq_english_sessions_one_active_child", table_name="english_practice_sessions")
    op.drop_index("ix_english_sessions_child_started", table_name="english_practice_sessions")
    op.drop_table("english_practice_sessions")
    op.drop_table("english_practice_settings")
