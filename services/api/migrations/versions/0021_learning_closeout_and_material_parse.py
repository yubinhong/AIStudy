"""Add evidence-backed review attempts and bounded curriculum parsing facts."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021_learning_closeout_parse"
down_revision: str | None = "0020_answer_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mistake_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verified_question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("answer_summary", sa.String(1000), nullable=False),
        sa.Column("submitted_answer", sa.String(1000), nullable=True),
        sa.Column("evidence_confirmed", sa.Boolean(), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("policy_version", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mistake_id"], ["mistake_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["verified_question_id"], ["verified_questions.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "outcome IN ('correct', 'needs_review', 'skipped')",
            name="ck_review_attempts_outcome",
        ),
    )
    op.create_index(
        "ix_review_attempts_child_created",
        "review_attempts",
        ["household_id", "child_id", "created_at"],
    )

    op.create_table(
        "material_parse_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parser_version", sa.String(80), nullable=False),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["learning_materials.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["curriculum_snapshots.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("material_id", name="uq_material_parse_jobs_material"),
        sa.CheckConstraint(
            "status IN ('uploaded', 'queued', 'parsing', 'needs_review', 'needs_ocr', "
            "'failed', 'quarantined', 'completed')",
            name="ck_material_parse_jobs_status",
        ),
    )
    op.create_index(
        "ix_material_parse_jobs_queue",
        "material_parse_jobs",
        ["status", "updated_at"],
    )

    op.create_table(
        "curriculum_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_sha256", sa.String(64), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("parser_version", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["learning_materials.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["curriculum_snapshots.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "material_id", "page_number", "chunk_index", name="uq_curriculum_chunks_page"
        ),
        sa.CheckConstraint("page_number >= 1", name="ck_curriculum_chunks_page"),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_curriculum_chunks_confidence"
        ),
    )
    op.create_index(
        "ix_curriculum_chunks_scope",
        "curriculum_chunks",
        ["household_id", "child_id", "snapshot_id", "page_number"],
    )

    op.drop_constraint("ck_learning_materials_status", "learning_materials", type_="check")
    op.create_check_constraint(
        "ck_learning_materials_status",
        "learning_materials",
        "status IN ('draft', 'uploaded', 'queued', 'parsing', 'needs_review', 'needs_ocr', "
        "'failed', 'quarantined', 'parsed', 'published', 'rejected', "
        "'unsupported_for_learning_content')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_learning_materials_status", "learning_materials", type_="check")
    op.create_check_constraint(
        "ck_learning_materials_status",
        "learning_materials",
        "status IN ('draft', 'uploaded', 'parsed', 'published', 'rejected')",
    )
    op.drop_index("ix_curriculum_chunks_scope", table_name="curriculum_chunks")
    op.drop_table("curriculum_chunks")
    op.drop_index("ix_material_parse_jobs_queue", table_name="material_parse_jobs")
    op.drop_table("material_parse_jobs")
    op.drop_index("ix_review_attempts_child_created", table_name="review_attempts")
    op.drop_table("review_attempts")
