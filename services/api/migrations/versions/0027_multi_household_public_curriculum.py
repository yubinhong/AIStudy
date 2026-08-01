"""Add household administrators and explicitly authorized public curriculum reuse.

Revision ID: 0027_multi_household
Revises: 0026_parallel_curriculum
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0027_multi_household"
down_revision: str | None = "0026_parallel_curriculum"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Login has no household selector. Usernames must therefore identify exactly
    # one account across every self-hosted family.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM accounts GROUP BY username HAVING COUNT(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'cannot make account usernames global: duplicate usernames exist';
            END IF;
        END $$;
        """
    )
    op.drop_constraint("uq_accounts_household_username", "accounts", type_="unique")
    op.create_unique_constraint("uq_accounts_username", "accounts", ["username"])
    op.drop_constraint("ck_accounts_role", "accounts", type_="check")
    op.drop_constraint("ck_accounts_child_binding", "accounts", type_="check")
    op.execute("UPDATE accounts SET role = 'parent_admin' WHERE role = 'parent'")
    op.create_check_constraint(
        "ck_accounts_role",
        "accounts",
        "role IN ('parent_admin', 'parent', 'child')",
    )
    op.create_check_constraint(
        "ck_accounts_child_binding",
        "accounts",
        "(role = 'child' AND child_id IS NOT NULL) "
        "OR (role IN ('parent_admin', 'parent') AND child_id IS NULL)",
    )

    # Only an explicit parent declaration permits cross-household reuse. The
    # public source is still invisible to other tenants; it is resolved only in
    # the private import transaction after the complete file hash is verified.
    op.add_column(
        "learning_materials",
        sa.Column("is_public_reusable", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.drop_index("ix_learning_materials_object_key", table_name="learning_materials")
    op.create_index("ix_learning_materials_object_key", "learning_materials", ["object_key"])
    op.create_index(
        "ix_learning_materials_public_content",
        "learning_materials",
        ["content_sha256", "media_type", "byte_size"],
        postgresql_where=sa.text("is_public_reusable = true AND object_key IS NOT NULL"),
    )
    op.add_column(
        "curriculum_snapshots",
        sa.Column("reused_from_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_curriculum_snapshots_reused_from",
        "curriculum_snapshots",
        "curriculum_snapshots",
        ["reused_from_snapshot_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint(
        "uq_curriculum_page_assets_object_key", "curriculum_page_assets", type_="unique"
    )
    op.create_index(
        "ix_curriculum_page_assets_object_key", "curriculum_page_assets", ["object_key"]
    )


def downgrade() -> None:
    op.drop_index("ix_curriculum_page_assets_object_key", table_name="curriculum_page_assets")
    op.create_unique_constraint(
        "uq_curriculum_page_assets_object_key", "curriculum_page_assets", ["object_key"]
    )
    op.drop_constraint(
        "fk_curriculum_snapshots_reused_from", "curriculum_snapshots", type_="foreignkey"
    )
    op.drop_column("curriculum_snapshots", "reused_from_snapshot_id")
    op.drop_index("ix_learning_materials_public_content", table_name="learning_materials")
    op.drop_index("ix_learning_materials_object_key", table_name="learning_materials")
    op.create_index(
        "ix_learning_materials_object_key", "learning_materials", ["object_key"], unique=True
    )
    op.drop_column("learning_materials", "is_public_reusable")
    op.drop_constraint("ck_accounts_child_binding", "accounts", type_="check")
    op.drop_constraint("ck_accounts_role", "accounts", type_="check")
    op.execute("UPDATE accounts SET role = 'parent' WHERE role = 'parent_admin'")
    op.create_check_constraint("ck_accounts_role", "accounts", "role IN ('parent', 'child')")
    op.create_check_constraint(
        "ck_accounts_child_binding",
        "accounts",
        "(role = 'child' AND child_id IS NOT NULL) OR (role = 'parent' AND child_id IS NULL)",
    )
    op.drop_constraint("uq_accounts_username", "accounts", type_="unique")
    op.create_unique_constraint(
        "uq_accounts_household_username", "accounts", ["household_id", "username"]
    )
