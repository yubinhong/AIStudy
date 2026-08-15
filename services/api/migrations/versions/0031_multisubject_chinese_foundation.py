"""Add subject-aware curriculum and deterministic Chinese practice facts.

Revision ID: 0031_multisubject_chinese
Revises: 0030_learning_history_retention
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0031_multisubject_chinese"
down_revision: str | None = "0030_learning_history_retention"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_child_profiles_supported_subjects", "child_profiles", type_="check")
    op.create_check_constraint(
        "ck_child_profiles_supported_subjects",
        "child_profiles",
        "subjects <@ ARRAY['math', 'chinese']::varchar[]",
    )

    for table_name in ("learning_materials", "curriculum_snapshots"):
        op.add_column(
            table_name,
            sa.Column("subject", sa.String(length=32), nullable=True),
        )
        op.execute(sa.text(f"UPDATE {table_name} SET subject = 'math' WHERE subject IS NULL"))
        op.alter_column(table_name, "subject", nullable=False)
        op.create_check_constraint(
            f"ck_{table_name}_subject",
            table_name,
            "subject IN ('math', 'chinese')",
        )

    op.create_index(
        "ix_learning_materials_household_child_subject",
        "learning_materials",
        ["household_id", "child_id", "subject", "created_at"],
    )
    op.create_index(
        "ix_curriculum_snapshots_household_child_subject",
        "curriculum_snapshots",
        ["household_id", "child_id", "subject", "status", "created_at"],
    )

    op.create_table(
        "chinese_content_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("revision", sa.Integer(), primary_key=True),
        sa.Column("grade_min", sa.SmallInteger(), nullable=False),
        sa.Column("grade_max", sa.SmallInteger(), nullable=False),
        sa.Column("skill", sa.String(length=32), nullable=False),
        sa.Column("task_group", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("content_json", postgresql.JSONB(), nullable=False),
        sa.Column("answer_spec_json", postgresql.JSONB(), nullable=False),
        sa.Column("knowledge_key", sa.String(length=120), nullable=False),
        sa.Column("difficulty", sa.String(length=16), nullable=False),
        sa.Column("source_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "grade_min BETWEEN 1 AND 6 AND grade_max BETWEEN grade_min AND 6",
            name="ck_chinese_content_grade_range",
        ),
        sa.CheckConstraint(
            "skill IN ('pinyin', 'character', 'vocabulary', 'sentence', 'reading', "
            "'recitation', 'expression')",
            name="ck_chinese_content_skill",
        ),
        sa.CheckConstraint(
            "difficulty IN ('basic', 'standard', 'advanced')",
            name="ck_chinese_content_difficulty",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'retired')",
            name="ck_chinese_content_status",
        ),
    )
    op.create_index(
        "ix_chinese_content_grade_skill_status",
        "chinese_content_items",
        ["grade_min", "grade_max", "skill", "status"],
    )
    op.create_table(
        "chinese_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_revision", sa.Integer(), nullable=False),
        sa.Column("response_json", postgresql.JSONB(), nullable=False),
        sa.Column("result_json", postgresql.JSONB(), nullable=False),
        sa.Column("scoring_version", sa.String(length=40), nullable=False),
        sa.Column("elapsed_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["content_id", "content_revision"],
            ["chinese_content_items.id", "chinese_content_items.revision"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("elapsed_ms BETWEEN 0 AND 1800000", name="ck_chinese_attempt_elapsed"),
    )
    op.create_index(
        "ix_chinese_attempts_household_child_created",
        "chinese_attempts",
        ["household_id", "child_id", "created_at", "id"],
    )
    op.create_table(
        "chinese_review_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_revision", sa.Integer(), nullable=False),
        sa.Column("skill", sa.String(length=32), nullable=False),
        sa.Column("knowledge_key", sa.String(length=120), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("strength", sa.SmallInteger(), nullable=False),
        sa.Column("last_feedback_tag", sa.String(length=80), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["content_id", "content_revision"],
            ["chinese_content_items.id", "chinese_content_items.revision"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("strength BETWEEN 0 AND 5", name="ck_chinese_review_strength"),
        sa.UniqueConstraint(
            "household_id", "child_id", "content_id", name="uq_chinese_review_child_content"
        ),
    )
    op.create_index(
        "ix_chinese_review_items_due",
        "chinese_review_items",
        ["household_id", "child_id", "due_at"],
    )

    op.execute(
        sa.text(
            """
            INSERT INTO chinese_content_items (
                id, revision, grade_min, grade_max, skill, task_group, title,
                content_json, answer_spec_json, knowledge_key, difficulty,
                source_json, status, created_at
            ) VALUES
            (
                '10000000-0000-0000-0000-000000000001', 1, 1, 2,
                'pinyin', 'language_accumulation', '声调辨一辨',
                $json${
                    "prompt":"选择读音为 qing（第一声）的汉字。",
                    "options":["青","请","庆"]
                }$json$::jsonb,
                $json${"type":"exact_choice","answer":"青"}$json$::jsonb,
                'pinyin-qing-tone-1', 'basic',
                $json${
                    "type":"original",
                    "source_id":"study-synthetic-chinese-v1",
                    "license_status":"cleared",
                    "attribution":"AIStudy original synthetic starter content"
                }$json$::jsonb,
                'approved', CURRENT_TIMESTAMP
            ),
            (
                '10000000-0000-0000-0000-000000000002', 1, 2, 4,
                'sentence', 'language_accumulation', '句子排排队',
                $json${"prompt":"把词语排成一句通顺的话。","options":["小树","长出了","嫩绿的","新叶"]}$json$::jsonb,
                $json${"type":"ordered_tokens","tokens":["小树","长出了","嫩绿的","新叶"]}$json$::jsonb,
                'sentence-basic-order', 'basic',
                $json${
                    "type":"original",
                    "source_id":"study-synthetic-chinese-v1",
                    "license_status":"cleared",
                    "attribution":"AIStudy original synthetic starter content"
                }$json$::jsonb,
                'approved', CURRENT_TIMESTAMP
            ),
            (
                '10000000-0000-0000-0000-000000000003', 1, 3, 6,
                'reading', 'literary_reading_expression', '从文中找依据',
                $json${"passage":"春风吹来，小树长出了嫩绿的新叶。小鸟站在枝头唱起了歌。","prompt":"为什么说小树感受到了春天？请回答并写出文中的依据。"}$json$::jsonb,
                $json${"type":"concept_evidence","required_concepts":[["新叶","嫩叶","长叶子"]],"evidence_spans":["小树长出了嫩绿的新叶"]}$json$::jsonb,
                'reading-find-evidence', 'basic',
                $json${
                    "type":"original",
                    "source_id":"study-synthetic-chinese-v1",
                    "license_status":"cleared",
                    "attribution":"AIStudy original synthetic starter content"
                }$json$::jsonb,
                'approved', CURRENT_TIMESTAMP
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_chinese_review_items_due", table_name="chinese_review_items")
    op.drop_table("chinese_review_items")
    op.drop_index("ix_chinese_attempts_household_child_created", table_name="chinese_attempts")
    op.drop_table("chinese_attempts")
    op.drop_index("ix_chinese_content_grade_skill_status", table_name="chinese_content_items")
    op.drop_table("chinese_content_items")
    op.drop_index(
        "ix_curriculum_snapshots_household_child_subject", table_name="curriculum_snapshots"
    )
    op.drop_index("ix_learning_materials_household_child_subject", table_name="learning_materials")
    for table_name in ("curriculum_snapshots", "learning_materials"):
        op.drop_constraint(f"ck_{table_name}_subject", table_name, type_="check")
        op.drop_column(table_name, "subject")
    op.drop_constraint("ck_child_profiles_supported_subjects", "child_profiles", type_="check")
    op.create_check_constraint(
        "ck_child_profiles_supported_subjects",
        "child_profiles",
        "subjects <@ ARRAY['math']::varchar[]",
    )
