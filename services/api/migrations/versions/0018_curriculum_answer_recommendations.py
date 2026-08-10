"""Add curriculum snapshots, explicit answer states and task recommendations.

Revision ID: 0018_curriculum_answer_recommendations
Revises: 0017_mistake_review
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_curriculum_recommendations"
down_revision: str | None = "0017_mistake_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "attempts",
        sa.Column("answer_state", sa.String(length=32), nullable=False, server_default="unclear"),
    )
    op.add_column(
        "attempts",
        sa.Column("evidence_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_check_constraint(
        "ck_attempts_answer_state",
        "attempts",
        "answer_state IN ('worked', 'blank', 'unclear', 'answer_area_missing')",
    )
    op.add_column(
        "tutor_turns",
        sa.Column("mode", sa.String(length=32), nullable=False, server_default="guided_practice"),
    )
    op.add_column(
        "tutor_turns",
        sa.Column("answer_state", sa.String(length=32), nullable=True),
    )

    op.create_table(
        "learning_materials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=160), nullable=False),
        sa.Column("media_type", sa.String(length=80), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("authorization_statement", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"], ondelete="CASCADE"),
        sa.CheckConstraint("byte_size >= 0", name="ck_learning_materials_size"),
        sa.CheckConstraint(
            "status IN ('draft', 'parsed', 'published', 'rejected')",
            name="ck_learning_materials_status",
        ),
    )
    op.create_index(
        "ix_learning_materials_household_child",
        "learning_materials",
        ["household_id", "child_id", "created_at"],
    )
    op.create_table(
        "curriculum_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("grade", sa.SmallInteger(), nullable=False),
        sa.Column("textbook_version", sa.String(length=120), nullable=False),
        sa.Column("term", sa.String(length=40), nullable=False),
        sa.Column("sections", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["learning_materials.id"], ondelete="CASCADE"),
        sa.CheckConstraint("grade BETWEEN 1 AND 6", name="ck_curriculum_snapshots_grade"),
        sa.CheckConstraint("version >= 1", name="ck_curriculum_snapshots_version"),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'rejected')",
            name="ck_curriculum_snapshots_status",
        ),
    )
    op.create_index(
        "ix_curriculum_snapshots_household_child_status",
        "curriculum_snapshots",
        ["household_id", "child_id", "status", "created_at"],
    )
    op.create_table(
        "task_recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mistake_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("reason", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mistake_id"], ["mistake_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["curriculum_snapshots.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["study_tasks.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_task_recommendations_status",
        ),
        sa.UniqueConstraint("child_id", "mistake_id", name="uq_task_recommendations_mistake"),
    )
    op.create_index(
        "ix_task_recommendations_household_child_status",
        "task_recommendations",
        ["household_id", "child_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_task_recommendations_household_child_status", table_name="task_recommendations"
    )
    op.drop_table("task_recommendations")
    op.drop_index(
        "ix_curriculum_snapshots_household_child_status", table_name="curriculum_snapshots"
    )
    op.drop_table("curriculum_snapshots")
    op.drop_index("ix_learning_materials_household_child", table_name="learning_materials")
    op.drop_table("learning_materials")
    op.drop_column("tutor_turns", "answer_state")
    op.drop_column("tutor_turns", "mode")
    op.drop_constraint("ck_attempts_answer_state", "attempts", type_="check")
    op.drop_column("attempts", "evidence_confirmed")
    op.drop_column("attempts", "answer_state")
