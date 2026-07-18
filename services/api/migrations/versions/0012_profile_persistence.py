"""Persist household child profiles and registered devices.

Revision ID: 0012_profile_persistence
Revises: 0011_account_password_session
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_profile_persistence"
down_revision: str | None = "0011_account_password_session"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "child_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("grade", sa.SmallInteger(), nullable=False),
        sa.Column("curriculum_version", sa.String(length=80), nullable=False),
        sa.Column(
            "subjects",
            postgresql.ARRAY(sa.String(length=32)),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("grade BETWEEN 1 AND 6", name="ck_child_profiles_grade"),
        sa.CheckConstraint(
            "cardinality(subjects) >= 1", name="ck_child_profiles_subjects_not_empty"
        ),
        sa.CheckConstraint(
            "subjects <@ ARRAY['math']::varchar[]",
            name="ck_child_profiles_supported_subjects",
        ),
        sa.UniqueConstraint("id", "household_id", name="uq_child_profiles_id_household"),
    )
    op.create_index(
        "ix_child_profiles_household_created",
        "child_profiles",
        ["household_id", "created_at", "id"],
    )
    op.create_table(
        "devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('child', 'parent')", name="ck_devices_kind"),
        sa.CheckConstraint("platform IN ('ios', 'android', 'web')", name="ck_devices_platform"),
        sa.CheckConstraint("status = 'active'", name="ck_devices_status"),
    )
    op.create_index(
        "ix_devices_household_registered",
        "devices",
        ["household_id", "registered_at", "id"],
    )

    # Preserve the deterministic profile exposed by every pre-0012 deployment.
    op.execute(
        sa.text(
            """
            INSERT INTO child_profiles (
                id, household_id, display_name, grade, curriculum_version,
                subjects, created_at, updated_at
            ) VALUES (
                '00000000-0000-0000-0000-000000000101',
                '00000000-0000-0000-0000-000000000001',
                'Synthetic Child A', 3, 'math-demo-2026',
                ARRAY['math']::varchar[],
                TIMESTAMPTZ '2026-01-01 00:00:00+00',
                TIMESTAMPTZ '2026-01-01 00:00:00+00'
            )
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    # A child account is already durable. Materialize any profile binding that
    # only existed in the old process memory and use its username as the least
    # surprising recoverable display name.
    op.execute(
        sa.text(
            """
            INSERT INTO child_profiles (
                id, household_id, display_name, grade, curriculum_version,
                subjects, created_at, updated_at
            )
            SELECT DISTINCT ON (child_id)
                child_id, household_id, username, 3, 'math-demo-2026',
                ARRAY['math']::varchar[], created_at, updated_at
            FROM accounts
            WHERE role = 'child' AND child_id IS NOT NULL
            ORDER BY child_id, created_at
            ON CONFLICT (id) DO UPDATE
            SET display_name = EXCLUDED.display_name,
                household_id = EXCLUDED.household_id,
                updated_at = EXCLUDED.updated_at
            """
        )
    )
    op.create_index("ix_accounts_child_id", "accounts", ["child_id"])
    op.create_foreign_key(
        "fk_accounts_child_profile",
        "accounts",
        "child_profiles",
        ["child_id", "household_id"],
        ["id", "household_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_accounts_child_profile", "accounts", type_="foreignkey")
    op.drop_index("ix_accounts_child_id", table_name="accounts")
    op.drop_index("ix_devices_household_registered", table_name="devices")
    op.drop_table("devices")
    op.drop_index("ix_child_profiles_household_created", table_name="child_profiles")
    op.drop_table("child_profiles")
