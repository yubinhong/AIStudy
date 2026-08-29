"""Replace legacy rhyme distractors in approved classical poem questions.

Revision ID: 0038_classical_poem_options
Revises: 0037_classical_poem_gate
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0038_classical_poem_options"
down_revision: str | None = "0037_classical_poem_gate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Keep IDs and answer specs stable so Attempt/Review references remain valid.
    op.execute(
        sa.text(
            """
            UPDATE chinese_content_items
            SET content_json = jsonb_set(
                    content_json,
                    '{options}',
                    CASE
                      WHEN regexp_replace(title, '[[:space:]（）()·《》]', '', 'g') = '咏鹅'
                        THEN jsonb_build_array(
                          answer_spec_json ->> 'answer', '远看山有色，', '江南可采莲，'
                        )
                      WHEN regexp_replace(title, '[[:space:]（）()·《》]', '', 'g') = '画'
                        THEN jsonb_build_array(
                          answer_spec_json ->> 'answer', '鹅，鹅，鹅，', '江南可采莲，'
                        )
                      ELSE jsonb_build_array(
                        answer_spec_json ->> 'answer', '鹅，鹅，鹅，', '远看山有色，'
                      )
                    END,
                    false
                  ),
                source_json = jsonb_set(
                    source_json,
                    '{attribution}',
                    to_jsonb(
                      '家庭已审核教材诗文；仅用于本家庭学习；classical-poem-catalog.v2'::text
                    ),
                    true
                  )
            WHERE status = 'approved'
              AND skill = 'poem'
              AND task_group = 'poem_spot_check'
              AND source_json ->> 'type' = 'private_curriculum'
              AND regexp_replace(
                    regexp_replace(title, '[[:space:]（）()·《》]', '', 'g'),
                    '节选$', '', 'g'
                  ) IN ('春晓', '咏鹅', '画', '悯农其二', '江南', '古朗月行', '风')
              AND answer_spec_json ->> 'type' = 'exact_choice'
            """
        )
    )


def downgrade() -> None:
    # Restoring unreviewed rhyme distractors would reintroduce child-facing content.
    pass
