"""Retire curriculum poem questions that are not recognized classical poems.

Revision ID: 0037_classical_poem_gate
Revises: 0036_task_session_progress
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0037_classical_poem_gate"
down_revision: str | None = "0036_task_session_progress"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Retiring keeps historical Attempt/Review foreign keys intact while removing
    # broad Provider classifications such as nursery rhymes from the child picker.
    op.execute(
        sa.text(
            """
            UPDATE chinese_content_items
            SET status = 'retired'
            WHERE status = 'approved'
              AND skill = 'poem'
              AND task_group = 'poem_spot_check'
              AND source_json ->> 'type' = 'private_curriculum'
              AND regexp_replace(
                    regexp_replace(title, '[[:space:]（）()·《》]', '', 'g'),
                    '节选$', '', 'g'
                  ) NOT IN ('春晓', '咏鹅', '画', '悯农其二', '江南', '古朗月行', '风')
            """
        )
    )


def downgrade() -> None:
    # Re-approving rejected candidates would reintroduce unsafe child content.
    # Keep the retired state and use a forward catalog expansion when warranted.
    pass
