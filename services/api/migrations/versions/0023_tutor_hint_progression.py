"""Persist Tutor hint progression metadata."""

import sqlalchemy as sa
from alembic import op

revision = "0023_tutor_hint_progression"
down_revision = "0022_tutor_curriculum_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tutor_turns",
        sa.Column(
            "hint_goal",
            sa.String(length=80),
            nullable=False,
            server_default="understand_the_question",
        ),
    )
    op.add_column("tutor_turns", sa.Column("builds_on_turn_id", sa.Uuid(), nullable=True))
    op.add_column(
        "tutor_turns",
        sa.Column("revealed_elements", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "tutor_turns",
        sa.Column(
            "child_action",
            sa.String(length=300),
            nullable=False,
            server_default="用自己的话说出下一步。",
        ),
    )
    op.add_column(
        "tutor_turns",
        sa.Column("answer_exposure", sa.String(length=20), nullable=False, server_default="none"),
    )
    op.create_foreign_key(
        "fk_tutor_turns_builds_on_turn",
        "tutor_turns",
        "tutor_turns",
        ["builds_on_turn_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_tutor_turns_answer_exposure",
        "tutor_turns",
        "answer_exposure IN ('none', 'partial', 'full')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_tutor_turns_answer_exposure", "tutor_turns", type_="check")
    op.drop_constraint("fk_tutor_turns_builds_on_turn", "tutor_turns", type_="foreignkey")
    for name in (
        "answer_exposure",
        "child_action",
        "revealed_elements",
        "builds_on_turn_id",
        "hint_goal",
    ):
        op.drop_column("tutor_turns", name)
