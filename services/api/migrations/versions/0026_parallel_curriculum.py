"""Keep curriculum snapshots independently published.

Revision ID: 0026_parallel_curriculum
Revises: 0025_curriculum_knowledge_map
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0026_parallel_curriculum"
down_revision: str | None = "0025_curriculum_knowledge_map"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # `rejected` was written only by the removed automatic replacement rule;
    # restoring it preserves the original immutable snapshot and approval facts.
    op.execute(
        "UPDATE curriculum_snapshots "
        "SET status = 'published', published_at = COALESCE(published_at, created_at) "
        "WHERE status = 'rejected'"
    )


def downgrade() -> None:
    # A downgrade must not silently deactivate independently published textbooks.
    pass
