"""Persist private page previews and parent-approved curriculum knowledge maps.

Revision ID: 0025_curriculum_knowledge_map
Revises: 0024_intelligent_recommendations
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025_curriculum_knowledge_map"
down_revision: str | None = "0024_intelligent_recommendations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "curriculum_page_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(32), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("image_sha256", sa.String(64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("renderer_version", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["learning_materials.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["curriculum_snapshots.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "snapshot_id", "page_number", name="uq_curriculum_page_assets_snapshot_page"
        ),
        sa.UniqueConstraint("object_key", name="uq_curriculum_page_assets_object_key"),
        sa.CheckConstraint("page_number >= 1", name="ck_curriculum_page_assets_page"),
        sa.CheckConstraint(
            "byte_size BETWEEN 1 AND 2097152",
            name="ck_curriculum_page_assets_bytes",
        ),
        sa.CheckConstraint(
            "width BETWEEN 1 AND 4000 AND height BETWEEN 1 AND 4000",
            name="ck_curriculum_page_assets_dimensions",
        ),
    )
    op.create_index(
        "ix_curriculum_page_assets_scope",
        "curriculum_page_assets",
        ["household_id", "child_id", "snapshot_id", "page_number"],
    )

    op.create_table(
        "curriculum_knowledge_maps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("book_summary", sa.Text(), nullable=True),
        sa.Column(
            "chapters",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("analyzed_page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider", sa.String(80), nullable=True),
        sa.Column("model", sa.String(160), nullable=True),
        sa.Column("schema_version", sa.String(80), nullable=False),
        sa.Column("prompt_version", sa.String(80), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=True),
        sa.Column("output_fingerprint", sa.String(64), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_cents", sa.Numeric(12, 4), nullable=True),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["learning_materials.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["curriculum_snapshots.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("snapshot_id", name="uq_curriculum_knowledge_maps_snapshot"),
        sa.CheckConstraint(
            "status IN ('queued', 'analyzing', 'needs_review', 'approved', 'failed')",
            name="ck_curriculum_knowledge_maps_status",
        ),
        sa.CheckConstraint(
            "page_count >= 0 AND analyzed_page_count >= 0 AND analyzed_page_count <= page_count",
            name="ck_curriculum_knowledge_maps_page_counts",
        ),
    )
    op.create_index(
        "ix_curriculum_knowledge_maps_queue",
        "curriculum_knowledge_maps",
        ["status", "updated_at"],
    )

    op.create_table(
        "curriculum_page_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("knowledge_map_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("chapter_title", sa.String(160), nullable=False),
        sa.Column("section_title", sa.String(160), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "knowledge_observations",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("model", sa.String(160), nullable=False),
        sa.Column("schema_version", sa.String(80), nullable=False),
        sa.Column("prompt_version", sa.String(80), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("output_fingerprint", sa.String(64), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_cents", sa.Numeric(12, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["learning_materials.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["curriculum_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["knowledge_map_id"], ["curriculum_knowledge_maps.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "knowledge_map_id",
            "page_number",
            name="uq_curriculum_page_analyses_map_page",
        ),
        sa.CheckConstraint("page_number >= 1", name="ck_curriculum_page_analyses_page"),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_curriculum_page_analyses_confidence",
        ),
    )
    op.create_index(
        "ix_curriculum_page_analyses_scope",
        "curriculum_page_analyses",
        ["household_id", "child_id", "snapshot_id", "page_number"],
    )

    op.create_table(
        "curriculum_knowledge_points",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("knowledge_map_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("knowledge_key", sa.String(80), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("chapter_title", sa.String(160), nullable=False),
        sa.Column("section_title", sa.String(160), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "learning_objectives",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "prerequisites",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "page_numbers",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "exercises",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["learning_materials.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["curriculum_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["knowledge_map_id"], ["curriculum_knowledge_maps.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "knowledge_map_id",
            "knowledge_key",
            name="uq_curriculum_knowledge_points_map_key",
        ),
        sa.CheckConstraint("order_index >= 0", name="ck_curriculum_knowledge_points_order"),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_curriculum_knowledge_points_confidence",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'rejected')",
            name="ck_curriculum_knowledge_points_status",
        ),
    )
    op.create_index(
        "ix_curriculum_knowledge_points_scope",
        "curriculum_knowledge_points",
        ["household_id", "child_id", "snapshot_id", "status", "order_index"],
    )

    for table_name in ("task_recommendations", "study_tasks"):
        op.add_column(
            table_name,
            sa.Column(
                "knowledge_point_id",
                postgresql.UUID(as_uuid=True),
                nullable=True,
            ),
        )
        op.create_foreign_key(
            f"fk_{table_name}_knowledge_point",
            table_name,
            "curriculum_knowledge_points",
            ["knowledge_point_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    for table_name in ("study_tasks", "task_recommendations"):
        op.drop_constraint(
            f"fk_{table_name}_knowledge_point",
            table_name,
            type_="foreignkey",
        )
        op.drop_column(table_name, "knowledge_point_id")
    op.drop_index(
        "ix_curriculum_knowledge_points_scope",
        table_name="curriculum_knowledge_points",
    )
    op.drop_table("curriculum_knowledge_points")
    op.drop_index(
        "ix_curriculum_page_analyses_scope",
        table_name="curriculum_page_analyses",
    )
    op.drop_table("curriculum_page_analyses")
    op.drop_index(
        "ix_curriculum_knowledge_maps_queue",
        table_name="curriculum_knowledge_maps",
    )
    op.drop_table("curriculum_knowledge_maps")
    op.drop_index(
        "ix_curriculum_page_assets_scope",
        table_name="curriculum_page_assets",
    )
    op.drop_table("curriculum_page_assets")
