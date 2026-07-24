"""Local full-corpus ranking and strict resolution for cloud-planned tasks."""

from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from study_api.domain.curriculum_knowledge import CurriculumKnowledgePoint
from study_api.domain.mistake_repository import MistakeWithSchedule
from study_api.domain.models import TaskExercise, TaskSourceType
from study_api.domain.recommendation_repository import RecommendationDraft

STRATEGY_VERSION = "source-bound-plan.v1"


class RecommendationSource(BaseModel):
    """A locally verified source candidate that may be exposed to the planner."""

    model_config = ConfigDict(frozen=True)

    source_key: str = Field(min_length=1, max_length=96)
    source_type: Literal["mistake", "curriculum"]
    question_text: str = Field(min_length=1, max_length=4000)
    knowledge_point: str = Field(min_length=1, max_length=120)
    mistake_id: UUID | None = None
    snapshot_id: UUID | None = None
    curriculum_chunk_id: UUID | None = None
    knowledge_point_id: UUID | None = None
    knowledge_key: str | None = Field(default=None, max_length=80)
    source_title: str | None = Field(default=None, max_length=160)
    source_page: int | None = Field(default=None, ge=1)
    visual_description: str | None = Field(default=None, max_length=1000)
    requires_visual_context: bool = False
    mistake_frequency: int = Field(default=0, ge=0)
    review_due: bool = False
    local_score: float = Field(ge=0)


class ProviderRecommendationItem(BaseModel):
    """One bounded plan item returned by the cloud planner."""

    source_keys: tuple[str, ...] = Field(min_length=1, max_length=3)
    title: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=240)
    knowledge_point: str = Field(min_length=1, max_length=120)
    scheduled_offset_days: int = Field(ge=0, le=6)
    estimated_minutes: int = Field(ge=5, le=45)


class ProviderRecommendationPlan(BaseModel):
    items: tuple[ProviderRecommendationItem, ...] = Field(min_length=1, max_length=5)


_KNOWLEDGE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("同时发生与经过时间", ("同时", "一起", "同一时间", "经过", "分钟", "小时")),
    ("分数的认识与比较", ("分数", "几分之", "分子", "分母", "通分")),
    ("倍数与数量关系", ("倍", "几倍", "倍数", "扩大", "缩小")),
    ("平均数与平均分", ("平均", "平均分", "每份", "每组")),
    ("加减数量关系", ("一共", "还剩", "相差", "多多少", "少多少", "增加", "减少")),
    ("乘除与分组", ("每个", "每人", "平均每", "分成", "乘法", "除法")),
    ("图形与测量", ("周长", "面积", "厘米", "米", "角", "长方形", "正方形")),
)


def classify_knowledge_point(text: str) -> str:
    normalized = "".join(text.split()).lower()
    if any(keyword in normalized for keyword in ("分数", "几分之", "分子", "分母", "通分")):
        return "分数的认识与比较"
    if any(keyword in normalized for keyword in ("同时", "同一时间")) and any(
        keyword in normalized for keyword in ("分钟", "小时", "时间", "经过")
    ):
        return "同时发生与经过时间"
    scored = [
        (sum(normalized.count(keyword) for keyword in keywords), label)
        for label, keywords in _KNOWLEDGE_PATTERNS
    ]
    score, label = max(scored)
    return label if score > 0 else "数学应用与计算"


def extract_exercises(text: str) -> tuple[str, ...]:
    """Extract exact question-like passages without generating textbook content."""

    normalized = re.sub(r"[ \t]+", " ", text.replace("\r", "\n"))
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    candidates: list[str] = []
    for index, line in enumerate(lines):
        has_question_mark = "？" in line or "?" in line
        has_exercise_marker = bool(
            re.search(r"(例\s*\d+|练习|做一做|想一想|算一算|解决问题|第\s*\d+\s*题)", line)
        )
        has_math_expression = bool(re.search(r"(?:\d\s*[+\-×÷=]\s*\d|[+\-×÷=]\s*\d)", line))
        has_task_wording = any(
            word in line for word in ("计算", "求", "填", "列式", "多少", "几", "比较")
        )
        follows_exercise_heading = any(
            re.search(r"(练习|做一做|想一想|算一算|解决问题)", previous)
            for previous in lines[max(0, index - 3) : index]
        )
        if not (
            has_question_mark
            or has_exercise_marker
            or (has_math_expression and (has_task_wording or follows_exercise_heading))
        ):
            continue
        start = max(0, index - 1 if len(line) < 24 else index)
        candidate = " ".join(lines[start : index + 1])
        candidate = candidate[-1200:].strip()
        if len(candidate) < 6 or candidate in candidates:
            continue
        candidates.append(candidate)
        if len(candidates) >= 3:
            break
    return tuple(candidates)


def build_recommendation_sources(
    mistakes: list[MistakeWithSchedule],
    knowledge_points: list[CurriculumKnowledgePoint],
    *,
    now: datetime | None = None,
    cloud_candidate_limit: int = 30,
) -> tuple[RecommendationSource, ...]:
    """Rank approved knowledge/exercises and every open mistake locally."""

    current = now or datetime.now(UTC)
    matched_points: dict[UUID, CurriculumKnowledgePoint | None] = {}
    point_frequencies: Counter[UUID] = Counter()
    fallback_frequencies: Counter[str] = Counter()
    for item in mistakes:
        if item.question is None:
            continue
        point = _best_knowledge_point(item.question.question_text, knowledge_points)
        matched_points[item.mistake.id] = point
        if point is not None:
            point_frequencies[point.id] += 1
        else:
            fallback_frequencies[classify_knowledge_point(item.question.question_text)] += 1
    mistake_sources: list[RecommendationSource] = []
    for item in mistakes:
        if item.question is None:
            continue
        question_text = item.question.question_text.strip()
        matched = matched_points.get(item.mistake.id)
        knowledge_point = (
            matched.title if matched is not None else classify_knowledge_point(question_text)
        )
        frequency = (
            point_frequencies[matched.id]
            if matched is not None
            else fallback_frequencies[knowledge_point]
        )
        due = item.schedule.due_at <= current
        mistake_sources.append(
            RecommendationSource(
                source_key=f"mistake:{item.mistake.id}",
                source_type="mistake",
                question_text=question_text,
                knowledge_point=knowledge_point,
                mistake_id=item.mistake.id,
                knowledge_point_id=matched.id if matched is not None else None,
                knowledge_key=matched.knowledge_key if matched is not None else None,
                mistake_frequency=frequency,
                review_due=due,
                local_score=100 + frequency * 20 + (30 if due else 0),
            )
        )

    curriculum_sources: list[RecommendationSource] = []
    for point in knowledge_points:
        if point.status != "approved":
            continue
        weak_frequency = point_frequencies[point.id]
        for exercise_index, exercise in enumerate(point.exercises):
            curriculum_sources.append(
                RecommendationSource(
                    source_key=f"curriculum:{point.id}:{exercise_index}",
                    source_type="curriculum",
                    question_text=exercise.question_text,
                    knowledge_point=point.title,
                    snapshot_id=point.snapshot_id,
                    knowledge_point_id=point.id,
                    knowledge_key=point.knowledge_key,
                    source_title=f"{point.chapter_title} · {point.section_title}",
                    source_page=exercise.page_number,
                    visual_description=exercise.visual_description,
                    requires_visual_context=exercise.requires_visual_context,
                    mistake_frequency=weak_frequency,
                    local_score=40 + weak_frequency * 25 + exercise.confidence * 10,
                )
            )

    mistake_sources.sort(
        key=lambda source: (
            source.review_due,
            source.mistake_frequency,
            source.local_score,
            source.source_key,
        ),
        reverse=True,
    )
    curriculum_sources.sort(
        key=lambda source: (
            source.mistake_frequency,
            source.local_score,
            -int(source.source_page or 0),
            source.source_key,
        ),
        reverse=True,
    )
    # Preserve both jobs: actual mistake review and follow-up exercises from the PDF.
    mistake_quota = min(len(mistake_sources), max(1, cloud_candidate_limit // 2))
    selected = mistake_sources[:mistake_quota]
    selected.extend(curriculum_sources[: cloud_candidate_limit - len(selected)])
    if len(selected) < cloud_candidate_limit:
        selected.extend(
            mistake_sources[mistake_quota : cloud_candidate_limit - len(selected) + mistake_quota]
        )
    return tuple(selected[:cloud_candidate_limit])


def _best_knowledge_point(
    question_text: str, points: list[CurriculumKnowledgePoint]
) -> CurriculumKnowledgePoint | None:
    """Deterministically link a mistake to the closest approved textbook concept."""

    question_tokens = _bigrams(question_text)
    best: CurriculumKnowledgePoint | None = None
    best_score = 0.0
    for point in points:
        if point.status != "approved":
            continue
        description = " ".join(
            (
                point.title,
                point.summary,
                *point.learning_objectives,
                *(exercise.question_text for exercise in point.exercises),
                *(exercise.visual_description or "" for exercise in point.exercises),
            )
        )
        point_tokens = _bigrams(description)
        if not question_tokens or not point_tokens:
            continue
        overlap = len(question_tokens & point_tokens)
        score = overlap / max(1, min(len(question_tokens), len(point_tokens)))
        if score > best_score:
            best, best_score = point, score
    return best if best_score >= 0.08 else None


def _bigrams(value: str) -> set[str]:
    normalized = "".join(character for character in value if not character.isspace())
    return {normalized[index : index + 2] for index in range(max(0, len(normalized) - 1))}


def resolve_provider_plan(
    plan: ProviderRecommendationPlan,
    sources: tuple[RecommendationSource, ...],
    *,
    today: date,
    provider: str,
    model: str,
) -> tuple[RecommendationDraft, ...]:
    """Resolve opaque keys back to exact local questions and reject hallucinated sources."""

    by_key = {source.source_key: source for source in sources}
    selected_items: list[tuple[ProviderRecommendationItem, tuple[RecommendationSource, ...]]] = []
    for item in plan.items:
        try:
            selected_items.append((item, tuple(by_key[key] for key in item.source_keys)))
        except KeyError as error:
            raise ValueError("recommendation references an unknown source key") from error
    available_types = {source.source_type for source in sources}
    selected_types = {source.source_type for _, resolved in selected_items for source in resolved}
    if "mistake" in available_types and "mistake" not in selected_types:
        raise ValueError("recommendation ignores the child's open mistakes")
    if "curriculum" in available_types and "curriculum" not in selected_types:
        raise ValueError("recommendation ignores available curriculum exercises")
    due_keys = {source.source_key for source in sources if source.review_due}
    if due_keys and not any(
        item.scheduled_offset_days == 0 and bool(due_keys.intersection(item.source_keys))
        for item, _ in selected_items
    ):
        raise ValueError("due mistake review must be scheduled for today")

    daily_counts: Counter[date] = Counter()
    seen_plan_keys: set[str] = set()
    drafts: list[RecommendationDraft] = []
    for item, resolved in selected_items:
        if len(set(item.source_keys)) != len(item.source_keys):
            raise ValueError("recommendation item repeats a source key")
        scheduled_for = today + timedelta(days=item.scheduled_offset_days)
        daily_counts[scheduled_for] += 1
        if daily_counts[scheduled_for] > 3:
            raise ValueError("recommendation exceeds the daily task limit")
        plan_key = f"{scheduled_for}:{'|'.join(sorted(item.source_keys))}"
        if plan_key in seen_plan_keys:
            raise ValueError("recommendation repeats the same sources on one day")
        seen_plan_keys.add(plan_key)

        source_types = {source.source_type for source in resolved}
        source_type = (
            TaskSourceType.MIXED_PLAN
            if len(source_types) > 1
            else TaskSourceType.MISTAKE_REVIEW
            if source_types == {"mistake"}
            else TaskSourceType.CURRICULUM_EXERCISE
        )
        exercises = tuple(
            TaskExercise(
                question_text=source.question_text,
                source_type=source.source_type,
                mistake_id=source.mistake_id,
                snapshot_id=source.snapshot_id,
                curriculum_chunk_id=source.curriculum_chunk_id,
                knowledge_point_id=source.knowledge_point_id,
                knowledge_key=source.knowledge_key,
                source_title=source.source_title,
                source_page=source.source_page,
                visual_description=source.visual_description,
                requires_visual_context=source.requires_visual_context,
            )
            for source in resolved
        )
        local_knowledge_point = Counter(source.knowledge_point for source in resolved).most_common(
            1
        )[0][0]
        stable_key = sha256(plan_key.encode()).hexdigest()[:40]
        drafts.append(
            RecommendationDraft(
                source_type=source_type,
                source_key=f"plan:{stable_key}",
                mistake_id=next(
                    (source.mistake_id for source in resolved if source.mistake_id),
                    None,
                ),
                snapshot_id=next(
                    (source.snapshot_id for source in resolved if source.snapshot_id),
                    None,
                ),
                curriculum_chunk_id=next(
                    (
                        source.curriculum_chunk_id
                        for source in resolved
                        if source.curriculum_chunk_id
                    ),
                    None,
                ),
                knowledge_point_id=next(
                    (source.knowledge_point_id for source in resolved if source.knowledge_point_id),
                    None,
                ),
                title=item.title,
                reason=item.reason,
                # The provider may explain or schedule the task, but it cannot
                # promote an arbitrary label to a learning fact.
                knowledge_point=local_knowledge_point,
                exercises=exercises,
                estimated_minutes=item.estimated_minutes,
                scheduled_for=scheduled_for,
                strategy_version=STRATEGY_VERSION,
                provider=provider,
                model=model,
            )
        )
    return tuple(drafts)


def planner_payload(sources: tuple[RecommendationSource, ...]) -> list[dict]:
    """Return the bounded fields permitted to cross the cloud planning boundary."""

    return [
        {
            "source_key": source.source_key,
            "source_type": source.source_type,
            "question_text": source.question_text[:1200],
            "knowledge_point": source.knowledge_point,
            "source_title": source.source_title,
            "source_page": source.source_page,
            "knowledge_key": source.knowledge_key,
            "visual_description": source.visual_description,
            "requires_visual_context": source.requires_visual_context,
            "mistake_frequency": source.mistake_frequency,
            "review_due": source.review_due,
        }
        for source in sources
    ]
