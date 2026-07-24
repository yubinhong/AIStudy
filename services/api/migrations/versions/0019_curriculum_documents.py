"""Store uploaded curriculum documents in the private object store."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_curriculum_documents"
down_revision: str | None = "0018_curriculum_recommendations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "learning_materials",
        sa.Column("object_key", sa.String(length=512), nullable=True),
    )
    op.drop_constraint("ck_learning_materials_status", "learning_materials", type_="check")
    op.create_check_constraint(
        "ck_learning_materials_status",
        "learning_materials",
        "status IN ('draft', 'uploaded', 'parsed', 'published', 'rejected')",
    )
    op.create_index(
        "ix_learning_materials_object_key",
        "learning_materials",
        ["object_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_learning_materials_object_key", table_name="learning_materials")
    op.drop_constraint("ck_learning_materials_status", "learning_materials", type_="check")
    op.create_check_constraint(
        "ck_learning_materials_status",
        "learning_materials",
        "status IN ('draft', 'parsed', 'published', 'rejected')",
    )
    op.drop_column("learning_materials", "object_key")
