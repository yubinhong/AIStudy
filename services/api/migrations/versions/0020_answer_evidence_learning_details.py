"""Persist visual answer evidence and complete Tutor solutions.

Revision ID: 0020_answer_evidence
Revises: 0019_curriculum_documents
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_answer_evidence"
down_revision: str | None = "0019_curriculum_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ANSWER_STATES = "('worked', 'blank', 'unclear', 'answer_area_missing')"


def upgrade() -> None:
    op.add_column(
        "question_extractions",
        sa.Column("answer_state", sa.String(length=32), nullable=False, server_default="unclear"),
    )
    op.add_column(
        "question_extractions",
        sa.Column(
            "answer_state_confidence",
            sa.Numeric(precision=5, scale=4),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "question_extractions",
        sa.Column("answer_steps", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.create_check_constraint(
        "ck_question_extractions_answer_state",
        "question_extractions",
        f"answer_state IN {_ANSWER_STATES}",
    )
    op.create_check_constraint(
        "ck_question_extractions_answer_state_confidence",
        "question_extractions",
        "answer_state_confidence >= 0 AND answer_state_confidence <= 1",
    )

    op.add_column(
        "verified_questions",
        sa.Column("answer_state", sa.String(length=32), nullable=False, server_default="unclear"),
    )
    op.add_column(
        "verified_questions",
        sa.Column(
            "answer_state_confidence",
            sa.Numeric(precision=5, scale=4),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "verified_questions",
        sa.Column("answer_steps", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "verified_questions",
        sa.Column("evidence_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_check_constraint(
        "ck_verified_questions_answer_state",
        "verified_questions",
        f"answer_state IN {_ANSWER_STATES}",
    )
    op.create_check_constraint(
        "ck_verified_questions_answer_state_confidence",
        "verified_questions",
        "answer_state_confidence >= 0 AND answer_state_confidence <= 1",
    )

    op.add_column(
        "tutor_turns",
        sa.Column("solution_steps", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.add_column("tutor_turns", sa.Column("final_answer", sa.String(length=1000)))
    op.add_column("tutor_turns", sa.Column("verification", sa.String(length=1000)))
    op.add_column(
        "tutor_turns",
        sa.Column("requires_child_response", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("tutor_turns", "requires_child_response")
    op.drop_column("tutor_turns", "verification")
    op.drop_column("tutor_turns", "final_answer")
    op.drop_column("tutor_turns", "solution_steps")
    op.drop_constraint(
        "ck_verified_questions_answer_state_confidence", "verified_questions", type_="check"
    )
    op.drop_constraint("ck_verified_questions_answer_state", "verified_questions", type_="check")
    op.drop_column("verified_questions", "evidence_confirmed")
    op.drop_column("verified_questions", "answer_steps")
    op.drop_column("verified_questions", "answer_state_confidence")
    op.drop_column("verified_questions", "answer_state")
    op.drop_constraint(
        "ck_question_extractions_answer_state_confidence",
        "question_extractions",
        type_="check",
    )
    op.drop_constraint(
        "ck_question_extractions_answer_state", "question_extractions", type_="check"
    )
    op.drop_column("question_extractions", "answer_steps")
    op.drop_column("question_extractions", "answer_state_confidence")
    op.drop_column("question_extractions", "answer_state")
