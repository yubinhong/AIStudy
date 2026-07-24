"""Persist small, page-scoped curriculum citations on Tutor turns."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022_tutor_curriculum_sources"
down_revision: str | None = "0021_learning_closeout_parse"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tutor_turns",
        sa.Column(
            "curriculum_sources",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("tutor_turns", "curriculum_sources")
