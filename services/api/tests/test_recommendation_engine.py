from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest

from study_api.domain.curriculum_knowledge import (
    CurriculumKnowledgeExercise,
    CurriculumKnowledgePoint,
)
from study_api.domain.mistake_repository import (
    MistakeRecord,
    MistakeStatus,
    MistakeWithSchedule,
    ReviewQuestion,
    ReviewSchedule,
)
from study_api.domain.models import TaskSourceType
from study_api.recommendation_engine import (
    ProviderRecommendationItem,
    ProviderRecommendationPlan,
    build_recommendation_sources,
    resolve_provider_plan,
)

HOUSEHOLD_ID = UUID("00000000-0000-0000-0000-000000000001")
CHILD_ID = UUID("00000000-0000-0000-0000-000000000101")
SNAPSHOT_ID = UUID("00000000-0000-0000-0000-000000000201")
MATERIAL_ID = UUID("00000000-0000-0000-0000-000000000301")
NOW = datetime(2026, 7, 23, 8, tzinfo=UTC)


def _mistake(index: int, question_text: str, *, due: bool) -> MistakeWithSchedule:
    mistake_id = UUID(f"00000000-0000-0000-0000-{index:012d}")
    return MistakeWithSchedule(
        mistake=MistakeRecord(
            id=mistake_id,
            household_id=HOUSEHOLD_ID,
            child_id=CHILD_ID,
            verified_question_id=UUID(f"10000000-0000-0000-0000-{index:012d}"),
            session_id=UUID(f"20000000-0000-0000-0000-{index:012d}"),
            reason="需要复习",
            status=MistakeStatus.OPEN,
            created_at=NOW - timedelta(days=2),
        ),
        schedule=ReviewSchedule(
            id=UUID(f"30000000-0000-0000-0000-{index:012d}"),
            household_id=HOUSEHOLD_ID,
            child_id=CHILD_ID,
            mistake_id=mistake_id,
            due_at=NOW - timedelta(hours=1) if due else NOW + timedelta(days=1),
            interval_days=1,
            repetitions=0,
            created_at=NOW - timedelta(days=2),
            updated_at=NOW - timedelta(days=2),
        ),
        question=ReviewQuestion(
            id=UUID(f"40000000-0000-0000-0000-{index:012d}"),
            question_text=question_text,
            options=(),
            formulas=(),
        ),
    )


def _point(
    index: int,
    page: int,
    title: str,
    question: str,
    *,
    visual_description: str | None = None,
) -> CurriculumKnowledgePoint:
    return CurriculumKnowledgePoint(
        id=UUID(f"50000000-0000-0000-0000-{index:012d}"),
        household_id=HOUSEHOLD_ID,
        child_id=CHILD_ID,
        material_id=MATERIAL_ID,
        snapshot_id=SNAPSHOT_ID,
        knowledge_map_id=UUID("60000000-0000-0000-0000-000000000001"),
        knowledge_key=f"kp-test-{index}",
        order_index=index,
        chapter_title="测试章节",
        section_title=title,
        title=title,
        summary=f"掌握{title}的概念和方法",
        learning_objectives=(f"能解决{title}问题",),
        prerequisites=(),
        page_numbers=(page,),
        exercises=(
            CurriculumKnowledgeExercise(
                source_key=f"page:{page}:exercise:0",
                page_number=page,
                question_text=question,
                visual_description=visual_description,
                requires_visual_context=visual_description is not None,
                difficulty="basic",
                confidence=0.95,
            ),
        ),
        confidence=0.95,
        status="approved",
        created_at=NOW,
        updated_at=NOW,
    )


def test_approved_knowledge_scan_prefers_exercise_matching_frequent_mistake() -> None:
    mistakes = [
        _mistake(1, "一张纸平均分成4份，涂了1份，涂色部分是几分之几？", due=True),
        _mistake(2, "四分之一和三分之一，哪个分数更大？", due=False),
        _mistake(3, "四个人同时玩了40分钟，每人玩了多长时间？", due=False),
    ]
    points = [
        _point(1, 2, "图形与测量", "一个正方形边长4厘米，周长是多少？"),
        _point(
            2,
            86,
            "分数的初步认识",
            "把一个圆平均分成8份，涂出其中3份，涂色部分是几分之几？",
            visual_description="圆被平均分成八份，其中三份涂色",
        ),
    ]

    sources = build_recommendation_sources(mistakes, points, now=NOW)

    curriculum = [source for source in sources if source.source_type == "curriculum"]
    assert curriculum[0].source_page == 86
    assert curriculum[0].source_title == "测试章节 · 分数的初步认识"
    assert curriculum[0].mistake_frequency == 2
    assert curriculum[0].requires_visual_context is True
    assert "涂色部分是几分之几" in curriculum[0].question_text


def test_cloud_plan_resolves_to_exact_questions_and_future_task_metadata() -> None:
    mistakes = [_mistake(1, "四个人同时玩了40分钟，每人玩了多长时间？", due=False)]
    points = [
        _point(
            2,
            35,
            "同时发生与经过时间",
            "三名同学同时阅读了20分钟，每人阅读了多长时间？",
        )
    ]
    sources = build_recommendation_sources(mistakes, points, now=NOW)
    keys = {source.source_type: source.source_key for source in sources}
    plan = ProviderRecommendationPlan(
        items=(
            ProviderRecommendationItem(
                source_keys=(keys["mistake"], keys["curriculum"]),
                title="同时发生与经过时间巩固",
                reason="先复习原错题，再用教材第35页同类题确认是否真正理解。",
                knowledge_point="模型随意填写的知识点",
                scheduled_offset_days=2,
                estimated_minutes=12,
            ),
        )
    )

    drafts = resolve_provider_plan(
        plan,
        sources,
        today=date(2026, 7, 23),
        provider="newapi",
        model="math-model",
    )

    assert drafts[0].source_type is TaskSourceType.MIXED_PLAN
    assert drafts[0].knowledge_point == "同时发生与经过时间"
    assert drafts[0].scheduled_for == date(2026, 7, 25)
    assert drafts[0].estimated_minutes == 12
    assert [exercise.source_type for exercise in drafts[0].exercises] == [
        "mistake",
        "curriculum",
    ]
    assert drafts[0].exercises[1].source_page == 35
    assert drafts[0].exercises[1].question_text.endswith("每人阅读了多长时间？")


def test_cloud_plan_cannot_invent_a_question_source() -> None:
    sources = build_recommendation_sources(
        [_mistake(1, "四个人同时玩了40分钟，每人玩了多长时间？", due=True)],
        [],
        now=NOW,
    )
    plan = ProviderRecommendationPlan(
        items=(
            ProviderRecommendationItem(
                source_keys=("curriculum:invented:0",),
                title="不存在的题",
                reason="不能接受模型凭空生成的来源。",
                knowledge_point="数学应用与计算",
                scheduled_offset_days=0,
                estimated_minutes=10,
            ),
        )
    )

    with pytest.raises(ValueError, match="unknown source"):
        resolve_provider_plan(
            plan,
            sources,
            today=date(2026, 7, 23),
            provider="newapi",
            model="math-model",
        )
