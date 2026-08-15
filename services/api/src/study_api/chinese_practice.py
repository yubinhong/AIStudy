"""Versioned Chinese content and deterministic scoring."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from typing import Annotated, Any, Literal, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import MetaData, Table, create_engine, insert, select, update
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


class ChineseContentSource(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["original", "private_curriculum"]
    source_id: str = Field(min_length=1, max_length=120)
    license_status: Literal["cleared", "private_authorized"]
    attribution: str | None = Field(default=None, max_length=240)


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


class ChineseScoreResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    score: float = Field(ge=0)
    max_score: float = Field(gt=0)
    correct: bool
    feedback_tags: tuple[str, ...]
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
        return _binary_score(correct, "choice")
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
        self, grade: int, skill: ChineseSkill | None = None
    ) -> list[ChineseContentItem]: ...

    def submit_attempt(
        self,
        household_id: UUID,
        child_id: UUID,
        grade: int,
        request: ChineseAttemptRequest,
        idempotency_key: str,
    ) -> tuple[ChineseAttempt, bool]: ...


def _starter_content() -> tuple[ChineseContentItem, ...]:
    source = ChineseContentSource(
        type="original",
        source_id="study-synthetic-chinese-v1",
        license_status="cleared",
        attribution="AIStudy original synthetic starter content",
    )
    return (
        ChineseContentItem(
            id=UUID("10000000-0000-0000-0000-000000000001"),
            revision=1,
            grade_min=1,
            grade_max=2,
            skill=ChineseSkill.PINYIN,
            task_group="language_accumulation",
            title="声调辨一辨",
            prompt="选择读音为 qing（第一声）的汉字。",
            options=("青", "请", "庆"),
            answer_spec=ExactChoiceSpec(type="exact_choice", answer="青"),
            knowledge_key="pinyin-qing-tone-1",
            source=source,
        ),
        ChineseContentItem(
            id=UUID("10000000-0000-0000-0000-000000000002"),
            revision=1,
            grade_min=2,
            grade_max=4,
            skill=ChineseSkill.SENTENCE,
            task_group="language_accumulation",
            title="句子排排队",
            prompt="把词语排成一句通顺的话。",
            options=("小树", "长出了", "嫩绿的", "新叶"),
            answer_spec=OrderedTokensSpec(
                type="ordered_tokens", tokens=("小树", "长出了", "嫩绿的", "新叶")
            ),
            knowledge_key="sentence-basic-order",
            source=source,
        ),
        ChineseContentItem(
            id=UUID("10000000-0000-0000-0000-000000000003"),
            revision=1,
            grade_min=3,
            grade_max=6,
            skill=ChineseSkill.READING,
            task_group="literary_reading_expression",
            title="从文中找依据",
            passage="春风吹来，小树长出了嫩绿的新叶。小鸟站在枝头唱起了歌。",
            prompt="为什么说小树感受到了春天？请回答并写出文中的依据。",
            answer_spec=ConceptEvidenceSpec(
                type="concept_evidence",
                required_concepts=(("新叶", "嫩叶", "长叶子"),),
                evidence_spans=("小树长出了嫩绿的新叶",),
            ),
            knowledge_key="reading-find-evidence",
            source=source,
        ),
    )


class InMemoryChinesePracticeRepository:
    def __init__(self) -> None:
        self._content = {item.id: item for item in _starter_content()}
        self._attempts: dict[UUID, ChineseAttempt] = {}
        self._idempotency: dict[tuple[UUID, UUID, str], tuple[str, UUID]] = {}

    def list_content(
        self, grade: int, skill: ChineseSkill | None = None
    ) -> list[ChineseContentItem]:
        return [
            item
            for item in self._content.values()
            if item.status == "approved"
            and item.grade_min <= grade <= item.grade_max
            and (skill is None or item.skill is skill)
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
        self._idempotency[key] = (fingerprint, attempt.id)
        return attempt, False


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
        self, grade: int, skill: ChineseSkill | None = None
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
            return [self._item(dict(row)) for row in connection.execute(statement).mappings()]

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
            review = (
                connection.execute(
                    select(self._reviews).where(
                        self._reviews.c.household_id == household_id,
                        self._reviews.c.child_id == child_id,
                        self._reviews.c.content_id == item.id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            due_at = now + timedelta(days=3 if result.correct else 1)
            if review is None:
                connection.execute(
                    insert(self._reviews).values(
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
                )
            else:
                connection.execute(
                    update(self._reviews)
                    .where(self._reviews.c.id == review["id"])
                    .values(
                        content_revision=item.revision,
                        due_at=due_at,
                        strength=min(5, review["strength"] + 1) if result.correct else 0,
                        last_feedback_tag=result.feedback_tags[0],
                        updated_at=now,
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
