"""Ensure one child login account per household child profile."""

from collections.abc import Sequence

from alembic import op

revision: str = "0016_child_account_uniqueness"
down_revision: str | None = "0015_child_data_export"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM accounts
                WHERE role = 'child' AND child_id IS NOT NULL
                GROUP BY household_id, child_id
                HAVING COUNT(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'cannot create child account uniqueness index: duplicate child bindings exist';
            END IF;
        END $$;
        CREATE UNIQUE INDEX uq_accounts_household_child
        ON accounts (household_id, child_id)
        WHERE role = 'child' AND child_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_accounts_household_child")
