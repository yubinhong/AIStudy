"""Record the public source identity for selected curriculum imports."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0039_smartedu_curriculum_source"
down_revision: str | None = "0038_classical_poem_options"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "learning_materials",
        sa.Column("source_provider", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "learning_materials",
        sa.Column("source_resource_id", sa.String(length=120), nullable=True),
    )
    op.create_check_constraint(
        "ck_learning_materials_source_pair",
        "learning_materials",
        "(source_provider IS NULL AND source_resource_id IS NULL) "
        "OR (source_provider IS NOT NULL AND source_resource_id IS NOT NULL)",
    )
    op.create_index(
        "ix_learning_materials_source_identity",
        "learning_materials",
        ["source_provider", "source_resource_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_learning_materials_source_identity", table_name="learning_materials")
    op.drop_constraint("ck_learning_materials_source_pair", "learning_materials", type_="check")
    op.drop_column("learning_materials", "source_resource_id")
    op.drop_column("learning_materials", "source_provider")
