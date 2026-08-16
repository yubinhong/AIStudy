"""Add original Chinese MVP demonstration content.

Revision ID: 0032_chinese_original_content_pack
Revises: 0031_multisubject_chinese
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032_chinese_original_content_pack"
down_revision: str | None = "0031_multisubject_chinese"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO chinese_content_items (
                id, revision, grade_min, grade_max, skill, task_group, title,
                content_json, answer_spec_json, knowledge_key, difficulty,
                source_json, status, created_at
            ) VALUES
            ('10000000-0000-0000-0000-000000000004', 1, 1, 2,
             'character', 'language_accumulation', '偏旁找朋友',
             $json${
                "prompt":"选出和天气有关的汉字。",
                "options":["晴","清","请"]
             }$json$::jsonb,
             $json${"type":"exact_choice","answer":"晴"}$json$::jsonb,
             'character-sun-radical-weather', 'basic',
             $json${
                "type":"original",
                "source_id":"study-synthetic-chinese-v1",
                "license_status":"cleared",
                "attribution":"Original demo; owner review required"
             }$json$::jsonb,
             'approved', CURRENT_TIMESTAMP),
            ('10000000-0000-0000-0000-000000000005', 1, 2, 4,
             'vocabulary', 'language_accumulation', '词语放进句子',
             $json${
                "prompt":"早晨的空气很（  ），让人觉得舒服。",
                "options":["清新","安静","明亮"]
             }$json$::jsonb,
             $json${"type":"exact_choice","answer":"清新"}$json$::jsonb,
             'vocabulary-context-meaning', 'basic',
             $json${
                "type":"original",
                "source_id":"study-synthetic-chinese-v1",
                "license_status":"cleared",
                "attribution":"Original demo; owner review required"
             }$json$::jsonb,
             'approved', CURRENT_TIMESTAMP),
            ('10000000-0000-0000-0000-000000000006', 1, 1, 6,
             'recitation', 'literary_reading_expression', '原创短句积累',
             $json${
                "prompt":"晨风吹过小花园，下一句最合适的是哪一句？",
                "options":["小树向着太阳笑","月亮落在书包里","雨伞飞到操场上"]
             }$json$::jsonb,
             $json${"type":"exact_choice","answer":"小树向着太阳笑"}$json$::jsonb,
             'recitation-original-short-line', 'basic',
             $json${
                "type":"original",
                "source_id":"study-synthetic-chinese-v1",
                "license_status":"cleared",
                "attribution":"Original demo; owner review required"
             }$json$::jsonb,
             'approved', CURRENT_TIMESTAMP)
            ON CONFLICT (id, revision) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM chinese_content_items
            WHERE id IN (
                '10000000-0000-0000-0000-000000000004',
                '10000000-0000-0000-0000-000000000005',
                '10000000-0000-0000-0000-000000000006'
            )
            AND revision = 1
            """
        )
    )
