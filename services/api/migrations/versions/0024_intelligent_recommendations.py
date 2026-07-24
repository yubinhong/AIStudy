"""Add source-backed recommendation plans and deliverable task exercises.

Revision ID: 0024_intelligent_recommendations
Revises: 0023_tutor_hint_progression
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024_intelligent_recommendations"
down_revision: str | None = "0023_tutor_hint_progression"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "task_recommendations",
        sa.Column(
            "source_type",
            sa.String(length=32),
            nullable=False,
            server_default="manual",
        ),
    )
    op.add_column(
        "task_recommendations",
        sa.Column("source_key", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "task_recommendations",
        sa.Column(
            "curriculum_chunk_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "task_recommendations",
        sa.Column(
            "knowledge_point",
            sa.String(length=120),
            nullable=False,
            server_default="待确认知识点",
        ),
    )
    op.add_column(
        "task_recommendations",
        sa.Column(
            "exercises",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "task_recommendations",
        sa.Column(
            "estimated_minutes",
            sa.SmallInteger(),
            nullable=False,
            server_default="10",
        ),
    )
    op.add_column(
        "task_recommendations",
        sa.Column(
            "scheduled_for",
            sa.Date(),
            nullable=False,
            server_default=sa.text("CURRENT_DATE"),
        ),
    )
    op.add_column(
        "task_recommendations",
        sa.Column(
            "strategy_version",
            sa.String(length=80),
            nullable=False,
            server_default="legacy",
        ),
    )
    op.add_column(
        "task_recommendations",
        sa.Column(
            "provider",
            sa.String(length=80),
            nullable=False,
            server_default="legacy",
        ),
    )
    op.add_column(
        "task_recommendations",
        sa.Column(
            "model",
            sa.String(length=160),
            nullable=False,
            server_default="legacy",
        ),
    )
    op.execute(
        "UPDATE task_recommendations "
        "SET source_key = 'legacy:' || id::text "
        "WHERE source_key IS NULL"
    )
    op.alter_column("task_recommendations", "source_key", nullable=False)
    op.create_foreign_key(
        "fk_task_recommendations_curriculum_chunk",
        "task_recommendations",
        "curriculum_chunks",
        ["curriculum_chunk_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_task_recommendations_source_type",
        "task_recommendations",
        "source_type IN ('manual', 'mistake_review', 'curriculum_exercise', 'mixed_plan')",
    )
    op.create_check_constraint(
        "ck_task_recommendations_estimated_minutes",
        "task_recommendations",
        "estimated_minutes BETWEEN 5 AND 60",
    )
    op.drop_constraint(
        "uq_task_recommendations_mistake",
        "task_recommendations",
        type_="unique",
    )
    op.create_index(
        "uq_task_recommendations_pending_source",
        "task_recommendations",
        ["household_id", "child_id", "source_key", "scheduled_for"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.add_column(
        "study_tasks",
        sa.Column(
            "source_type",
            sa.String(length=32),
            nullable=False,
            server_default="manual",
        ),
    )
    op.add_column(
        "study_tasks",
        sa.Column("reason", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "study_tasks",
        sa.Column("knowledge_point", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "study_tasks",
        sa.Column(
            "exercises",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "study_tasks",
        sa.Column("estimated_minutes", sa.SmallInteger(), nullable=True),
    )
    op.create_check_constraint(
        "ck_study_tasks_source_type",
        "study_tasks",
        "source_type IN ('manual', 'mistake_review', 'curriculum_exercise', 'mixed_plan')",
    )
    op.create_check_constraint(
        "ck_study_tasks_estimated_minutes",
        "study_tasks",
        "estimated_minutes IS NULL OR estimated_minutes BETWEEN 1 AND 120",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_study_tasks_estimated_minutes",
        "study_tasks",
        type_="check",
    )
    op.drop_constraint("ck_study_tasks_source_type", "study_tasks", type_="check")
    for name in (
        "estimated_minutes",
        "exercises",
        "knowledge_point",
        "reason",
        "source_type",
    ):
        op.drop_column("study_tasks", name)

    op.drop_index(
        "uq_task_recommendations_pending_source",
        table_name="task_recommendations",
    )
    op.create_unique_constraint(
        "uq_task_recommendations_mistake",
        "task_recommendations",
        ["child_id", "mistake_id"],
    )
    op.drop_constraint(
        "ck_task_recommendations_estimated_minutes",
        "task_recommendations",
        type_="check",
    )
    op.drop_constraint(
        "ck_task_recommendations_source_type",
        "task_recommendations",
        type_="check",
    )
    op.drop_constraint(
        "fk_task_recommendations_curriculum_chunk",
        "task_recommendations",
        type_="foreignkey",
    )
    for name in (
        "model",
        "provider",
        "strategy_version",
        "scheduled_for",
        "estimated_minutes",
        "exercises",
        "knowledge_point",
        "curriculum_chunk_id",
        "source_key",
        "source_type",
    ):
        op.drop_column("task_recommendations", name)
