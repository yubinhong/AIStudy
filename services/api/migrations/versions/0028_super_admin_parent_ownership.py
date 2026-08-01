"""Replace per-family administrators with one super administrator.

Revision ID: 0028_super_admin_ownership
Revises: 0027_multi_household
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0028_super_admin_ownership"
down_revision: str | None = "0027_multi_household"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The earliest existing family administrator becomes the only instance-wide
    # super administrator. Every other family administrator is an ordinary
    # parent, so a newly provisioned family never receives an admin role.
    op.drop_constraint("ck_accounts_role", "accounts", type_="check")
    op.drop_constraint("ck_accounts_child_binding", "accounts", type_="check")
    op.execute(
        """
        WITH selected AS (
            SELECT id
            FROM accounts
            WHERE role = 'parent_admin'
            ORDER BY created_at, id
            LIMIT 1
        )
        UPDATE accounts
        SET role = CASE WHEN accounts.id = selected.id THEN 'super_admin' ELSE 'parent' END
        FROM selected
        WHERE accounts.role = 'parent_admin'
        """
    )
    op.create_check_constraint(
        "ck_accounts_role", "accounts", "role IN ('super_admin', 'parent', 'child')"
    )
    op.create_check_constraint(
        "ck_accounts_child_binding",
        "accounts",
        "(role = 'child' AND child_id IS NOT NULL) "
        "OR (role IN ('super_admin', 'parent') AND child_id IS NULL)",
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_accounts_single_super_admin "
        "ON accounts ((1)) WHERE role = 'super_admin'"
    )

    op.add_column(
        "child_profiles",
        sa.Column("owner_account_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    # Existing children keep their family and are assigned to the oldest
    # eligible adult in that family. The original admin household therefore
    # remains owned by the migrated super administrator.
    op.execute(
        """
        WITH ranked_adults AS (
            SELECT id, household_id,
                   row_number() OVER (
                       PARTITION BY household_id
                       ORDER BY CASE WHEN role = 'super_admin' THEN 0 ELSE 1 END, created_at, id
                   ) AS rank
            FROM accounts
            WHERE role IN ('super_admin', 'parent')
        )
        UPDATE child_profiles AS child
        SET owner_account_id = adult.id
        FROM ranked_adults AS adult
        WHERE child.household_id = adult.household_id
          AND adult.rank = 1
          AND child.owner_account_id IS NULL
        """
    )
    # `0012` materialized this synthetic profile before the first bootstrap
    # account existed. It is test/demo seed data, not a real child record, so
    # a brand-new database must not fail migration solely because of it.
    op.execute(
        """
        DELETE FROM child_profiles AS child
        WHERE child.id = '00000000-0000-0000-0000-000000000101'
          AND child.owner_account_id IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM accounts adult
              WHERE adult.household_id = child.household_id
                AND adult.role IN ('super_admin', 'parent')
          )
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM child_profiles WHERE owner_account_id IS NULL) THEN
                RAISE EXCEPTION 'cannot assign child profile owner: household has no parent';
            END IF;
        END $$;
        """
    )
    op.alter_column("child_profiles", "owner_account_id", nullable=False)
    op.create_index(
        "ix_child_profiles_household_owner_created",
        "child_profiles",
        ["household_id", "owner_account_id", "created_at", "id"],
    )
    op.create_foreign_key(
        "fk_child_profiles_owner_account",
        "child_profiles",
        "accounts",
        ["owner_account_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_child_profiles_owner_account", "child_profiles", type_="foreignkey")
    op.drop_index("ix_child_profiles_household_owner_created", table_name="child_profiles")
    op.drop_column("child_profiles", "owner_account_id")
    op.drop_index("uq_accounts_single_super_admin", table_name="accounts")
    op.drop_constraint("ck_accounts_child_binding", "accounts", type_="check")
    op.drop_constraint("ck_accounts_role", "accounts", type_="check")
    op.execute("UPDATE accounts SET role = 'parent_admin' WHERE role = 'super_admin'")
    op.create_check_constraint(
        "ck_accounts_role", "accounts", "role IN ('parent_admin', 'parent', 'child')"
    )
    op.create_check_constraint(
        "ck_accounts_child_binding",
        "accounts",
        "(role = 'child' AND child_id IS NOT NULL) "
        "OR (role IN ('parent_admin', 'parent') AND child_id IS NULL)",
    )
