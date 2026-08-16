"""Allow curriculum-derived poem spot-check content.

Revision ID: 0035_chinese_poem_skill
Revises: 0034_picture_writing_guides
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0035_chinese_poem_skill"
down_revision: str | None = "0034_picture_writing_guides"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_chinese_content_skill", "chinese_content_items", type_="check")
    op.create_check_constraint(
        "ck_chinese_content_skill",
        "chinese_content_items",
        "skill IN ('pinyin', 'character', 'vocabulary', 'sentence', 'reading', "
        "'recitation', 'expression', 'poem')",
    )


def downgrade() -> None:
    # Forward repair is required if poem rows exist; this only restores the
    # previous development schema after poem content has been retired externally.
    op.drop_constraint("ck_chinese_content_skill", "chinese_content_items", type_="check")
    op.create_check_constraint(
        "ck_chinese_content_skill",
        "chinese_content_items",
        "skill IN ('pinyin', 'character', 'vocabulary', 'sentence', 'reading', "
        "'recitation', 'expression')",
    )
