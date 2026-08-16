"""Retire synthetic Chinese content and support curriculum poem practice.

Revision ID: 0033_chinese_poem_spot_check
Revises: 0032_chinese_original_content_pack
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033_chinese_poem_spot_check"
down_revision: str | None = "0032_chinese_original_content_pack"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Historical attempts and review rows keep their foreign keys. Retiring the
    # content removes it from the child picker without deleting learning facts.
    op.execute(
        sa.text(
            """
            UPDATE chinese_content_items
            SET status = 'retired'
            WHERE id IN (
              '10000000-0000-0000-0000-000000000001',
              '10000000-0000-0000-0000-000000000002',
              '10000000-0000-0000-0000-000000000003',
              '10000000-0000-0000-0000-000000000004',
              '10000000-0000-0000-0000-000000000005',
              '10000000-0000-0000-0000-000000000006'
            )
            """
        )
    )


def downgrade() -> None:
    # Forward repair is required in production. This downgrade only exists for
    # disposable local databases; it never deletes historical learning facts.
    op.execute(
        sa.text(
            """
            UPDATE chinese_content_items
            SET status = 'approved'
            WHERE id IN (
              '10000000-0000-0000-0000-000000000001',
              '10000000-0000-0000-0000-000000000002',
              '10000000-0000-0000-0000-000000000003',
              '10000000-0000-0000-0000-000000000004',
              '10000000-0000-0000-0000-000000000005',
              '10000000-0000-0000-0000-000000000006'
            )
            """
        )
    )
