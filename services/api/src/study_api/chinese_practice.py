"""Versioned Chinese content and deterministic scoring."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from typing import Annotated, Any, Literal, Protocol
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import MetaData, Table, and_, create_engine, func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from study_api.database import database_url
from study_api.domain.repository import IdempotencyConflictError

SCORING_VERSION = "chinese-score.v1"


class ChineseSkill(StrEnum):
    PINYIN = "pinyin"
    CHARACTER = "character"
    VOCABULARY = "vocabulary"
    SENTENCE = "sentence"
    READING = "reading"
    RECITATION = "recitation"
    EXPRESSION = "expression"
    POEM = "poem"


class ExactChoiceSpec(BaseModel):
    type: Literal["exact_choice"]
    answer: str = Field(min_length=1, max_length=120)


class OrderedTokensSpec(BaseModel):
    type: Literal["ordered_tokens"]
    tokens: tuple[str, ...] = Field(min_length=2, max_length=20)


class NormalizedTextSetSpec(BaseModel):
    type: Literal["normalized_text_set"]
    accepted: tuple[str, ...] = Field(min_length=1, max_length=20)


class ConceptEvidenceSpec(BaseModel):
    type: Literal["concept_evidence"]
    required_concepts: tuple[tuple[str, ...], ...] = Field(min_length=1, max_length=6)
    evidence_spans: tuple[str, ...] = Field(min_length=1, max_length=8)


AnswerSpec = Annotated[
    ExactChoiceSpec | OrderedTokensSpec | NormalizedTextSetSpec | ConceptEvidenceSpec,
    Field(discriminator="type"),
]


class ChineseContentReview(BaseModel):
    """Auditable editorial/rightsholder review state for original content.

    ``approved`` is reserved for a real project-owner signoff. Demo content may
    remain technically available to exercise the product, but never becomes
    formal courseware merely because its source is original.
    """

    model_config = ConfigDict(frozen=True)

    status: Literal["pending_owner_review", "approved"] = "pending_owner_review"
    protocol_version: Literal["chinese-content-review.v1"] = "chinese-content-review.v1"
    rights_evidence_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    reviewed_at: datetime | None = None
    reviewer_role: Literal["project_owner"] | None = None


class ChineseContentSource(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["original", "private_curriculum"]
    source_id: str = Field(min_length=1, max_length=120)
    license_status: Literal["cleared", "private_authorized"]
    attribution: str | None = Field(default=None, max_length=240)
    household_id: UUID | None = None
    child_id: UUID | None = None
    material_id: UUID | None = None
    snapshot_id: UUID | None = None
    page_number: int | None = Field(default=None, ge=1, le=400)
    review: ChineseContentReview = Field(default_factory=ChineseContentReview)


class ChineseContentItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    revision: int = Field(ge=1)
    grade_min: int = Field(ge=1, le=6)
    grade_max: int = Field(ge=1, le=6)
    skill: ChineseSkill
    task_group: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    passage: str | None = Field(default=None, max_length=4000)
    prompt: str = Field(min_length=1, max_length=1000)
    options: tuple[str, ...] = Field(default=(), max_length=12)
    answer_spec: AnswerSpec
    knowledge_key: str = Field(min_length=1, max_length=120)
    difficulty: Literal["basic", "standard", "advanced"] = "basic"
    source: ChineseContentSource
    status: Literal["draft", "approved", "retired"] = "approved"


class ChineseContentItemView(BaseModel):
    """Child-facing content without the answer specification."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    revision: int
    grade_min: int
    grade_max: int
    skill: ChineseSkill
    task_group: str
    title: str
    passage: str | None
    prompt: str
    options: tuple[str, ...]
    knowledge_key: str
    difficulty: Literal["basic", "standard", "advanced"]
    source: ChineseContentSource

    @classmethod
    def from_item(cls, item: ChineseContentItem) -> ChineseContentItemView:
        return cls.model_validate(item.model_dump(exclude={"answer_spec", "status"}))


class ChineseAttemptRequest(BaseModel):
    content_id: UUID
    content_revision: int = Field(ge=1)
    response: dict[str, str | list[str]]
    elapsed_ms: int = Field(ge=0, le=30 * 60 * 1000)

    @field_validator("response")
    @classmethod
    def validate_response(cls, response: dict[str, str | list[str]]) -> dict[str, str | list[str]]:
        allowed_keys = {"choice", "tokens", "text", "answer", "evidence"}
        if not response or not response.keys() <= allowed_keys:
            raise ValueError("response contains unsupported fields")
        for value in response.values():
            if isinstance(value, str):
                if len(value) > 1000:
                    raise ValueError("response text is too long")
            elif len(value) > 20 or any(len(token) > 120 for token in value):
                raise ValueError("response tokens exceed the bounded limit")
        return response


class ChinesePoemDraft(BaseModel):
    """One private textbook poem after bounded extraction and parent review."""

    title: str = Field(min_length=1, max_length=160)
    page_number: int = Field(ge=1, le=400)
    lines: tuple[str, ...] = Field(min_length=2, max_length=80)

    @field_validator("lines")
    @classmethod
    def validate_lines(cls, lines: tuple[str, ...]) -> tuple[str, ...]:
        if any(not line.strip() or len(line) > 120 for line in lines):
            raise ValueError("poem lines must be non-empty and bounded")
        return tuple(line.strip() for line in lines)


class PublishChinesePoemsRequest(BaseModel):
    """Parent confirmation of poems extracted from one already-approved snapshot."""

    material_id: UUID
    snapshot_id: UUID
    poems: tuple[ChinesePoemDraft, ...] = Field(min_length=1, max_length=100)


class ChineseScoreResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    score: float = Field(ge=0)
    max_score: float = Field(gt=0)
    correct: bool
    feedback_tags: tuple[str, ...]
    # Deliberately populated only after a failed objective submission. It is
    # feedback for the child, never part of the content-list response.
    correct_answer: str | None = Field(default=None, max_length=120)
    scoring_version: Literal["chinese-score.v1"] = "chinese-score.v1"


class ChineseAttempt(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    household_id: UUID
    child_id: UUID
    content_id: UUID
    content_revision: int
    result: ChineseScoreResult
    elapsed_ms: int
    created_at: datetime


class ChineseAttemptExport(ChineseAttempt):
    response: dict[str, Any]


class ChineseReviewItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    household_id: UUID
    child_id: UUID
    content_id: UUID
    content_revision: int
    skill: ChineseSkill
    knowledge_key: str
    due_at: datetime
    strength: int = Field(ge=0, le=5)
    last_feedback_tag: str
    updated_at: datetime


class ChineseSkillSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    skill: ChineseSkill
    attempts: int = Field(ge=0)
    correct_attempts: int = Field(ge=0)
    due_reviews: int = Field(ge=0)
    last_attempt_at: datetime | None = None


class ChineseSkillReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    child_id: UUID
    generated_at: datetime
    skills: tuple[ChineseSkillSummary, ...]


@dataclass
class _SkillAccumulator:
    attempts: int = 0
    correct_attempts: int = 0
    due_reviews: int = 0
    last_attempt_at: datetime | None = None

    def to_summary(self, skill: ChineseSkill) -> ChineseSkillSummary:
        return ChineseSkillSummary(
            skill=skill,
            attempts=self.attempts,
            correct_attempts=self.correct_attempts,
            due_reviews=self.due_reviews,
            last_attempt_at=self.last_attempt_at,
        )


def normalize_chinese(text: str) -> str:
    """Normalize bounded learner text for deterministic comparison."""

    return re.sub(r"[\s，。！？、,.!?；;：:]", "", text.strip().lower())


def score_chinese(
    item: ChineseContentItem, response: dict[str, str | list[str]]
) -> ChineseScoreResult:
    """Score one approved item without calling an AI provider."""

    spec = item.answer_spec
    if isinstance(spec, ExactChoiceSpec):
        correct = response.get("choice") == spec.answer
        result = _binary_score(correct, "choice")
        return result if correct else result.model_copy(update={"correct_answer": spec.answer})
    if isinstance(spec, OrderedTokensSpec):
        tokens = response.get("tokens")
        correct = isinstance(tokens, list) and tuple(tokens) == spec.tokens
        return _binary_score(correct, "order")
    if isinstance(spec, NormalizedTextSetSpec):
        text = response.get("text")
        correct = isinstance(text, str) and normalize_chinese(text) in {
            normalize_chinese(value) for value in spec.accepted
        }
        return _binary_score(correct, "text")

    answer = response.get("answer")
    evidence = response.get("evidence")
    if not isinstance(answer, str) or not isinstance(evidence, str):
        return ChineseScoreResult(
            score=0,
            max_score=2,
            correct=False,
            feedback_tags=("answer_required", "evidence_required"),
        )
    answer_n = normalize_chinese(answer)
    evidence_n = normalize_chinese(evidence)
    concept_ok = all(
        any(normalize_chinese(alias) in answer_n for alias in aliases)
        for aliases in spec.required_concepts
    )
    evidence_ok = any(
        normalize_chinese(span) in evidence_n or evidence_n in normalize_chinese(span)
        for span in spec.evidence_spans
        if evidence_n
    )
    score = float(concept_ok) + float(evidence_ok)
    tags = tuple(
        tag
        for passed, tag in ((concept_ok, "concept_missing"), (evidence_ok, "evidence_missing"))
        if not passed
    ) or ("correct",)
    return ChineseScoreResult(
        score=score,
        max_score=2,
        correct=score == 2,
        feedback_tags=tags,
    )


def _binary_score(correct: bool, kind: str) -> ChineseScoreResult:
    return ChineseScoreResult(
        score=1 if correct else 0,
        max_score=1,
        correct=correct,
        feedback_tags=("correct",) if correct else (f"{kind}_retry",),
    )


class ChinesePracticeRepository(Protocol):
    def list_content(
        self,
        grade: int,
        skill: ChineseSkill | None = None,
        household_id: UUID | None = None,
        child_id: UUID | None = None,
    ) -> list[ChineseContentItem]: ...

    def submit_attempt(
        self,
        household_id: UUID,
        child_id: UUID,
        grade: int,
        request: ChineseAttemptRequest,
        idempotency_key: str,
    ) -> tuple[ChineseAttempt, bool]: ...

    def list_reviews(
        self, household_id: UUID, child_id: UUID, grade: int, due_only: bool
    ) -> list[ChineseReviewItem]: ...

    def skill_report(self, household_id: UUID, child_id: UUID) -> ChineseSkillReport: ...

    def publish_poems(
        self,
        household_id: UUID,
        child_id: UUID,
        grade: int,
        request: PublishChinesePoemsRequest,
    ) -> int: ...


def _starter_content() -> tuple[ChineseContentItem, ...]:
    # Production content is curriculum-scoped and requires parent approval.
    # Keeping this empty prevents demos from being mistaken for courseware.
    return ()


def _is_visible_to(item: ChineseContentItem, household_id: UUID, child_id: UUID) -> bool:
    """Original content is global; curriculum-derived content is household scoped."""

    if item.source.type == "original":
        return True
    return item.source.household_id == household_id and item.source.child_id == child_id


class InMemoryChinesePracticeRepository:
    def __init__(self) -> None:
        self._content = {item.id: item for item in _starter_content()}
        self._attempts: dict[UUID, ChineseAttempt] = {}
        self._reviews: dict[tuple[UUID, UUID, UUID], ChineseReviewItem] = {}
        self._idempotency: dict[tuple[UUID, UUID, str], tuple[str, UUID]] = {}

    def list_content(
        self,
        grade: int,
        skill: ChineseSkill | None = None,
        household_id: UUID | None = None,
        child_id: UUID | None = None,
    ) -> list[ChineseContentItem]:
        return [
            item
            for item in self._content.values()
            if item.status == "approved"
            and item.grade_min <= grade <= item.grade_max
            and (skill is None or item.skill is skill)
            and (
                household_id is None
                or child_id is None
                or _is_visible_to(item, household_id, child_id)
            )
        ]

    def submit_attempt(
        self,
        household_id: UUID,
        child_id: UUID,
        grade: int,
        request: ChineseAttemptRequest,
        idempotency_key: str,
    ) -> tuple[ChineseAttempt, bool]:
        fingerprint = sha256(request.model_dump_json().encode()).hexdigest()
        key = (household_id, child_id, idempotency_key)
        receipt = self._idempotency.get(key)
        if receipt is not None:
            if receipt[0] != fingerprint:
                raise IdempotencyConflictError
            return self._attempts[receipt[1]], True
        item = self._content.get(request.content_id)
        if (
            item is None
            or item.status != "approved"
            or not item.grade_min <= grade <= item.grade_max
            or not _is_visible_to(item, household_id, child_id)
        ):
            raise LookupError("content not found")
        if item.revision != request.content_revision:
            raise ValueError("content revision conflict")
        attempt = ChineseAttempt(
            id=uuid4(),
            household_id=household_id,
            child_id=child_id,
            content_id=item.id,
            content_revision=item.revision,
            result=score_chinese(item, request.response),
            elapsed_ms=request.elapsed_ms,
            created_at=datetime.now(UTC),
        )
        self._attempts[attempt.id] = attempt
        review_key = (household_id, child_id, item.id)
        previous = self._reviews.get(review_key)
        self._reviews[review_key] = ChineseReviewItem(
            id=previous.id if previous is not None else uuid4(),
            household_id=household_id,
            child_id=child_id,
            content_id=item.id,
            content_revision=item.revision,
            skill=item.skill,
            knowledge_key=item.knowledge_key,
            due_at=attempt.created_at + timedelta(days=3 if attempt.result.correct else 1),
            strength=min(5, previous.strength + 1)
            if attempt.result.correct and previous
            else 1
            if attempt.result.correct
            else 0,
            last_feedback_tag=attempt.result.feedback_tags[0],
            updated_at=attempt.created_at,
        )
        self._idempotency[key] = (fingerprint, attempt.id)
        return attempt, False

    def list_reviews(
        self, household_id: UUID, child_id: UUID, grade: int, due_only: bool
    ) -> list[ChineseReviewItem]:
        now = datetime.now(UTC)
        return sorted(
            (
                review
                for review in self._reviews.values()
                if review.household_id == household_id
                and review.child_id == child_id
                and (item := self._content.get(review.content_id)) is not None
                and item.revision == review.content_revision
                and item.status == "approved"
                and item.grade_min <= grade <= item.grade_max
                and (not due_only or review.due_at <= now)
            ),
            key=lambda review: (review.due_at, review.id),
        )

    def skill_report(self, household_id: UUID, child_id: UUID) -> ChineseSkillReport:
        now = datetime.now(UTC)
        summaries: dict[ChineseSkill, _SkillAccumulator] = {}
        for attempt in self._attempts.values():
            if attempt.household_id != household_id or attempt.child_id != child_id:
                continue
            item = self._content.get(attempt.content_id)
            if item is None:
                continue
            summary = summaries.setdefault(item.skill, _SkillAccumulator())
            summary.attempts += 1
            summary.correct_attempts += int(attempt.result.correct)
            last_attempt = summary.last_attempt_at
            if last_attempt is None or attempt.created_at > last_attempt:
                summary.last_attempt_at = attempt.created_at
        for review in self._reviews.values():
            if (
                review.household_id != household_id
                or review.child_id != child_id
                or review.due_at > now
            ):
                continue
            summary = summaries.setdefault(review.skill, _SkillAccumulator())
            summary.due_reviews += 1
        return ChineseSkillReport(
            child_id=child_id,
            generated_at=now,
            skills=tuple(
                summary.to_summary(skill)
                for skill, summary in sorted(summaries.items(), key=lambda entry: entry[0].value)
            ),
        )

    def publish_poems(
        self,
        household_id: UUID,
        child_id: UUID,
        grade: int,
        request: PublishChinesePoemsRequest,
    ) -> int:
        items = _poem_question_items(household_id, child_id, grade, request)
        self._content.update({item.id: item for item in items})
        return len(items)


class PostgresChinesePracticeRepository:
    def __init__(self, url: str | None = None) -> None:
        self._engine = create_engine(url or database_url(), pool_pre_ping=True)
        metadata = MetaData()
        self._content = Table("chinese_content_items", metadata, autoload_with=self._engine)
        self._attempts = Table("chinese_attempts", metadata, autoload_with=self._engine)
        self._reviews = Table("chinese_review_items", metadata, autoload_with=self._engine)
        self._idempotency = Table("idempotency_records", metadata, autoload_with=self._engine)

    @property
    def engine(self) -> Engine:
        return self._engine

    def close(self) -> None:
        self._engine.dispose()

    @staticmethod
    def _item(row: dict[str, Any]) -> ChineseContentItem:
        return ChineseContentItem(
            id=row["id"],
            revision=row["revision"],
            grade_min=row["grade_min"],
            grade_max=row["grade_max"],
            skill=row["skill"],
            task_group=row["task_group"],
            title=row["title"],
            passage=row["content_json"].get("passage"),
            prompt=row["content_json"]["prompt"],
            options=tuple(row["content_json"].get("options", ())),
            answer_spec=row["answer_spec_json"],
            knowledge_key=row["knowledge_key"],
            difficulty=row["difficulty"],
            source=row["source_json"],
            status=row["status"],
        )

    @staticmethod
    def _attempt(row: dict[str, Any]) -> ChineseAttempt:
        return ChineseAttempt(
            id=row["id"],
            household_id=row["household_id"],
            child_id=row["child_id"],
            content_id=row["content_id"],
            content_revision=row["content_revision"],
            result=ChineseScoreResult.model_validate(row["result_json"]),
            elapsed_ms=row["elapsed_ms"],
            created_at=row["created_at"],
        )

    def list_content(
        self,
        grade: int,
        skill: ChineseSkill | None = None,
        household_id: UUID | None = None,
        child_id: UUID | None = None,
    ) -> list[ChineseContentItem]:
        statement = select(self._content).where(
            self._content.c.status == "approved",
            self._content.c.grade_min <= grade,
            self._content.c.grade_max >= grade,
        )
        if skill is not None:
            statement = statement.where(self._content.c.skill == skill.value)
        statement = statement.order_by(self._content.c.skill, self._content.c.id)
        with self._engine.connect() as connection:
            items = [self._item(dict(row)) for row in connection.execute(statement).mappings()]
        if household_id is None or child_id is None:
            return items
        return [item for item in items if _is_visible_to(item, household_id, child_id)]

    def submit_attempt(
        self,
        household_id: UUID,
        child_id: UUID,
        grade: int,
        request: ChineseAttemptRequest,
        idempotency_key: str,
    ) -> tuple[ChineseAttempt, bool]:
        operation = f"chinese_attempt:{child_id}"
        fingerprint = sha256(request.model_dump_json().encode()).hexdigest()
        now = datetime.now(UTC)
        with self._engine.begin() as connection:
            receipt = (
                connection.execute(
                    select(self._idempotency).where(
                        self._idempotency.c.household_id == household_id,
                        self._idempotency.c.operation == operation,
                        self._idempotency.c.idempotency_key == idempotency_key,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if receipt is not None:
                if receipt["fingerprint"] != fingerprint:
                    raise IdempotencyConflictError
                attempt_row = (
                    connection.execute(
                        select(self._attempts).where(self._attempts.c.id == receipt["resource_id"])
                    )
                    .mappings()
                    .one()
                )
                return self._attempt(dict(attempt_row)), True
            content_row = (
                connection.execute(
                    select(self._content).where(
                        self._content.c.id == request.content_id,
                        self._content.c.status == "approved",
                        self._content.c.grade_min <= grade,
                        self._content.c.grade_max >= grade,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if content_row is None:
                raise LookupError("content not found")
            item = self._item(dict(content_row))
            if not _is_visible_to(item, household_id, child_id):
                raise LookupError("content not found")
            if item.revision != request.content_revision:
                raise ValueError("content revision conflict")
            result = score_chinese(item, request.response)
            attempt_id = uuid4()
            connection.execute(
                insert(self._attempts).values(
                    id=attempt_id,
                    household_id=household_id,
                    child_id=child_id,
                    content_id=item.id,
                    content_revision=item.revision,
                    response_json=request.response,
                    result_json=result.model_dump(mode="json"),
                    scoring_version=SCORING_VERSION,
                    elapsed_ms=request.elapsed_ms,
                    created_at=now,
                )
            )
            due_at = now + timedelta(days=3 if result.correct else 1)
            review_insert = pg_insert(self._reviews).values(
                id=uuid4(),
                household_id=household_id,
                child_id=child_id,
                content_id=item.id,
                content_revision=item.revision,
                skill=item.skill.value,
                knowledge_key=item.knowledge_key,
                due_at=due_at,
                strength=1 if result.correct else 0,
                last_feedback_tag=result.feedback_tags[0],
                updated_at=now,
            )
            connection.execute(
                review_insert.on_conflict_do_update(
                    constraint="uq_chinese_review_child_content",
                    set_={
                        "content_revision": item.revision,
                        "due_at": due_at,
                        "strength": (
                            func.least(5, self._reviews.c.strength + 1) if result.correct else 0
                        ),
                        "last_feedback_tag": result.feedback_tags[0],
                        "updated_at": now,
                    },
                )
            )
            connection.execute(
                insert(self._idempotency).values(
                    household_id=household_id,
                    operation=operation,
                    idempotency_key=idempotency_key,
                    fingerprint=fingerprint,
                    resource_type="chinese_attempt",
                    resource_id=attempt_id,
                    created_at=now,
                )
            )
            return ChineseAttempt(
                id=attempt_id,
                household_id=household_id,
                child_id=child_id,
                content_id=item.id,
                content_revision=item.revision,
                result=result,
                elapsed_ms=request.elapsed_ms,
                created_at=now,
            ), False

    def list_reviews(
        self, household_id: UUID, child_id: UUID, grade: int, due_only: bool
    ) -> list[ChineseReviewItem]:
        statement = (
            select(self._reviews)
            .join(
                self._content,
                and_(
                    self._content.c.id == self._reviews.c.content_id,
                    self._content.c.revision == self._reviews.c.content_revision,
                ),
            )
            .where(
                self._reviews.c.household_id == household_id,
                self._reviews.c.child_id == child_id,
                self._content.c.status == "approved",
                self._content.c.grade_min <= grade,
                self._content.c.grade_max >= grade,
            )
            .order_by(self._reviews.c.due_at, self._reviews.c.id)
        )
        if due_only:
            statement = statement.where(self._reviews.c.due_at <= datetime.now(UTC))
        with self._engine.connect() as connection:
            return [
                ChineseReviewItem.model_validate(dict(row))
                for row in connection.execute(statement).mappings()
            ]

    def skill_report(self, household_id: UUID, child_id: UUID) -> ChineseSkillReport:
        now = datetime.now(UTC)
        summaries: dict[ChineseSkill, _SkillAccumulator] = {}
        attempt_statement = (
            select(
                self._attempts.c.created_at,
                self._attempts.c.result_json,
                self._content.c.skill,
            )
            .join(
                self._content,
                and_(
                    self._content.c.id == self._attempts.c.content_id,
                    self._content.c.revision == self._attempts.c.content_revision,
                ),
            )
            .where(
                self._attempts.c.household_id == household_id,
                self._attempts.c.child_id == child_id,
            )
        )
        review_statement = (
            select(self._reviews.c.skill, func.count().label("due_reviews"))
            .where(
                self._reviews.c.household_id == household_id,
                self._reviews.c.child_id == child_id,
                self._reviews.c.due_at <= now,
            )
            .group_by(self._reviews.c.skill)
        )
        with self._engine.connect() as connection:
            for row in connection.execute(attempt_statement).mappings():
                skill = ChineseSkill(row["skill"])
                summary = summaries.setdefault(skill, _SkillAccumulator())
                summary.attempts += 1
                summary.correct_attempts += int(bool(row["result_json"].get("correct")))
                last_attempt = summary.last_attempt_at
                if last_attempt is None or row["created_at"] > last_attempt:
                    summary.last_attempt_at = row["created_at"]
            for row in connection.execute(review_statement).mappings():
                skill = ChineseSkill(row["skill"])
                summary = summaries.setdefault(skill, _SkillAccumulator())
                summary.due_reviews = int(row["due_reviews"])
        return ChineseSkillReport(
            child_id=child_id,
            generated_at=now,
            skills=tuple(
                summary.to_summary(skill)
                for skill, summary in sorted(summaries.items(), key=lambda entry: entry[0].value)
            ),
        )

    def publish_poems(
        self,
        household_id: UUID,
        child_id: UUID,
        grade: int,
        request: PublishChinesePoemsRequest,
    ) -> int:
        items = _poem_question_items(household_id, child_id, grade, request)
        with self._engine.begin() as connection:
            for item in items:
                statement = pg_insert(self._content).values(
                    id=item.id,
                    revision=item.revision,
                    grade_min=item.grade_min,
                    grade_max=item.grade_max,
                    skill=item.skill.value,
                    task_group=item.task_group,
                    title=item.title,
                    content_json={
                        "passage": item.passage,
                        "prompt": item.prompt,
                        "options": list(item.options),
                    },
                    answer_spec_json=item.answer_spec.model_dump(mode="json"),
                    knowledge_key=item.knowledge_key,
                    difficulty=item.difficulty,
                    source_json=item.source.model_dump(mode="json"),
                    status=item.status,
                    created_at=datetime.now(UTC),
                )
                connection.execute(
                    statement.on_conflict_do_update(
                        index_elements=[self._content.c.id, self._content.c.revision],
                        set_={
                            "content_json": statement.excluded.content_json,
                            "answer_spec_json": statement.excluded.answer_spec_json,
                            "source_json": statement.excluded.source_json,
                            "status": statement.excluded.status,
                        },
                    )
                )
        return len(items)


def _poem_question_items(
    household_id: UUID,
    child_id: UUID,
    grade: int,
    request: PublishChinesePoemsRequest,
) -> tuple[ChineseContentItem, ...]:
    """Compile reviewed poem lines into deterministic next-line questions.

    Only a prompt line and answer choices reach the learner. Full source text remains
    confined to the approved household snapshot and the server-side answer spec.
    """

    all_lines = tuple(dict.fromkeys(line for poem in request.poems for line in poem.lines))
    items: list[ChineseContentItem] = []
    for poem in request.poems:
        for index, answer in enumerate(poem.lines[1:]):
            clue = poem.lines[index]
            distractors = [line for line in all_lines if line != answer and line != clue][:2]
            options = tuple(dict.fromkeys((answer, *distractors)))
            stable_key = (
                f"{request.snapshot_id}:{poem.page_number}:{poem.title}:{index}:{clue}:{answer}"
            )
            source = ChineseContentSource(
                type="private_curriculum",
                source_id=f"curriculum-poem:{request.snapshot_id}:{poem.page_number}",
                license_status="private_authorized",
                attribution="家庭已审核教材诗文；仅用于本家庭学习",
                household_id=household_id,
                child_id=child_id,
                material_id=request.material_id,
                snapshot_id=request.snapshot_id,
                page_number=poem.page_number,
            )
            items.append(
                ChineseContentItem(
                    id=uuid5(NAMESPACE_URL, stable_key),
                    revision=1,
                    grade_min=grade,
                    grade_max=grade,
                    skill=ChineseSkill.POEM,
                    task_group="poem_spot_check",
                    title=poem.title,
                    prompt=f"“{clue}”的下一句是哪一句？",
                    options=options,
                    answer_spec=ExactChoiceSpec(type="exact_choice", answer=answer),
                    knowledge_key=f"poem:{request.snapshot_id}:{poem.page_number}:{index}",
                    source=source,
                )
            )
    return tuple(items)
