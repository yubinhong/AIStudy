"""Persistent mistake records and deterministic review schedules."""

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import MetaData, Table, create_engine, insert, select, update
from sqlalchemy.engine import Engine

from study_api.database import database_url
from study_api.domain.repository import IdempotencyConflictError


class MistakeStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class ReviewOutcome(StrEnum):
    CORRECT = "correct"
    NEEDS_REVIEW = "needs_review"
    SKIPPED = "skipped"


REVIEW_POLICY_VERSION = "review-policy.v2"
REVIEW_INTERVALS = (1, 3, 7, 14, 30)


class MistakeRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    household_id: UUID
    child_id: UUID
    verified_question_id: UUID
    session_id: UUID
    reason: str = Field(min_length=1, max_length=80)
    status: MistakeStatus
    created_at: datetime
    resolved_at: datetime | None = None


class ReviewSchedule(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    household_id: UUID
    child_id: UUID
    mistake_id: UUID
    due_at: datetime
    interval_days: int = Field(ge=1)
    repetitions: int = Field(ge=0)
    last_outcome: ReviewOutcome | None = None
    created_at: datetime
    updated_at: datetime


class ReviewAttempt(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    household_id: UUID
    child_id: UUID
    mistake_id: UUID
    verified_question_id: UUID
    answer_summary: str = Field(min_length=1, max_length=1000)
    submitted_answer: str | None = Field(default=None, max_length=1000)
    evidence_confirmed: bool
    outcome: ReviewOutcome
    policy_version: str = Field(min_length=1, max_length=80)
    created_at: datetime


class ReviewQuestion(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    question_text: str = Field(min_length=1, max_length=4000)
    options: tuple[str, ...] = Field(max_length=20)
    formulas: tuple[str, ...] = Field(max_length=50)


class CreateMistakeRequest(BaseModel):
    verified_question_id: UUID
    session_id: UUID
    reason: str = Field(min_length=1, max_length=80)


class ReviewMistakeRequest(BaseModel):
    """A new review is evidence-first; outcome remains a narrow old-client bridge."""

    answer_summary: str = Field(default="旧客户端未提交作答文本", min_length=1, max_length=1000)
    submitted_answer: str | None = Field(default=None, max_length=1000)
    evidence_confirmed: bool = False
    outcome: ReviewOutcome | None = None


class MistakeWithSchedule(BaseModel):
    model_config = ConfigDict(frozen=True)

    mistake: MistakeRecord
    schedule: ReviewSchedule
    question: ReviewQuestion | None = None


class MistakeCloseoutRequest(BaseModel):
    verified_question_id: UUID
    session_id: UUID
    outcome: str = Field(pattern=r"^(learned|needs_review|skipped)$")
    reason: str = Field(default="拍题讲解后需要复习", min_length=1, max_length=80)


class MistakeCloseoutResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: UUID
    outcome: str
    mistake: MistakeWithSchedule | None = None


class MistakeRepository(Protocol):
    def closeout(
        self,
        household_id: UUID,
        child_id: UUID,
        request: MistakeCloseoutRequest,
        idempotency_key: str,
    ) -> tuple[MistakeCloseoutResult, bool]: ...

    def create_mistake(
        self,
        household_id: UUID,
        child_id: UUID,
        request: CreateMistakeRequest,
        idempotency_key: str,
    ) -> tuple[MistakeWithSchedule, bool]: ...

    def list_mistakes(
        self, household_id: UUID, child_id: UUID, due_before: datetime | None = None
    ) -> list[MistakeWithSchedule]: ...

    def review_mistake(
        self,
        household_id: UUID,
        child_id: UUID,
        mistake_id: UUID,
        request: ReviewMistakeRequest,
        idempotency_key: str,
    ) -> tuple[MistakeWithSchedule, bool]: ...


def _next_interval(current: int, outcome: ReviewOutcome) -> int:
    if outcome is ReviewOutcome.NEEDS_REVIEW:
        return 1
    if outcome is ReviewOutcome.SKIPPED:
        return max(1, min(current, 3))
    try:
        index = REVIEW_INTERVALS.index(current)
    except ValueError:
        index = 0
    return REVIEW_INTERVALS[min(index + 1, len(REVIEW_INTERVALS) - 1)]


def _determine_review_outcome(
    request: ReviewMistakeRequest, expected_answer: str | None
) -> ReviewOutcome:
    if request.evidence_confirmed and request.submitted_answer and expected_answer:
        def normalize(value: str) -> str:
            return "".join(value.split()).lower()

        return (
            ReviewOutcome.CORRECT
            if normalize(request.submitted_answer) == normalize(expected_answer)
            else ReviewOutcome.NEEDS_REVIEW
        )
    # Compatibility for the pre-evidence client. New clients must provide evidence.
    if request.outcome is not None and request.answer_summary == "旧客户端未提交作答文本":
        return request.outcome
    return ReviewOutcome.NEEDS_REVIEW


class InMemoryMistakeRepository:
    def __init__(self) -> None:
        self._records: dict[UUID, MistakeWithSchedule] = {}
        self._receipts: dict[tuple[UUID, str, str], tuple[str, UUID]] = {}
        self._review_attempts: list[ReviewAttempt] = []
        self._closeout_results: dict[UUID, MistakeCloseoutResult] = {}

    def closeout(
        self,
        household_id: UUID,
        child_id: UUID,
        request: MistakeCloseoutRequest,
        idempotency_key: str,
    ) -> tuple[MistakeCloseoutResult, bool]:
        operation = f"mistake_closeout:{request.session_id}"
        fingerprint = _fingerprint(request)
        key = (household_id, operation, idempotency_key)
        existing = self._receipts.get(key)
        if existing is not None:
            if existing[0] != fingerprint:
                raise IdempotencyConflictError
            return self._closeout_results[existing[1]], True
        current = next(
            (
                value
                for value in self._records.values()
                if value.mistake.session_id == request.session_id
                and value.mistake.child_id == child_id
                and value.mistake.verified_question_id == request.verified_question_id
            ),
            None,
        )
        if request.outcome != "needs_review":
            result = MistakeCloseoutResult(
                session_id=request.session_id, outcome=request.outcome, mistake=current
            )
            result_id = uuid4()
            self._closeout_results[result_id] = result
            self._receipts[key] = (fingerprint, result_id)
            return result, False
        if current is None:
            mistake_result, _ = self.create_mistake(
                household_id,
                child_id,
                CreateMistakeRequest(
                    verified_question_id=request.verified_question_id,
                    session_id=request.session_id,
                    reason=request.reason,
                ),
                f"{idempotency_key}:mistake",
            )
        else:
            mistake_result = current
        closeout = MistakeCloseoutResult(
            session_id=request.session_id, outcome=request.outcome, mistake=mistake_result
        )
        result_id = uuid4()
        self._closeout_results[result_id] = closeout
        self._receipts[key] = (fingerprint, result_id)
        return closeout, False

    def create_mistake(
        self,
        household_id: UUID,
        child_id: UUID,
        request: CreateMistakeRequest,
        idempotency_key: str,
    ) -> tuple[MistakeWithSchedule, bool]:
        operation = f"create_mistake:{child_id}"
        fingerprint = _fingerprint(request)
        receipt_key = (household_id, operation, idempotency_key)
        existing = self._receipts.get(receipt_key)
        if existing is not None:
            if existing[0] != fingerprint:
                raise IdempotencyConflictError
            return self._records[existing[1]], True
        for value in self._records.values():
            if value.mistake.verified_question_id == request.verified_question_id:
                raise ValueError("mistake already exists")
        now = datetime.now(UTC)
        mistake = MistakeRecord(
            id=uuid4(),
            household_id=household_id,
            child_id=child_id,
            verified_question_id=request.verified_question_id,
            session_id=request.session_id,
            reason=request.reason,
            status=MistakeStatus.OPEN,
            created_at=now,
        )
        schedule = ReviewSchedule(
            id=uuid4(),
            household_id=household_id,
            child_id=child_id,
            mistake_id=mistake.id,
            due_at=now + timedelta(days=1),
            interval_days=1,
            repetitions=0,
            created_at=now,
            updated_at=now,
        )
        result = MistakeWithSchedule(mistake=mistake, schedule=schedule)
        self._records[mistake.id] = result
        self._receipts[receipt_key] = (fingerprint, mistake.id)
        return result, False

    def list_mistakes(
        self, household_id: UUID, child_id: UUID, due_before: datetime | None = None
    ) -> list[MistakeWithSchedule]:
        values = [
            value
            for value in self._records.values()
            if value.mistake.household_id == household_id
            and value.mistake.child_id == child_id
            and value.mistake.status is MistakeStatus.OPEN
            and (due_before is None or value.schedule.due_at <= due_before)
        ]
        return sorted(values, key=lambda value: (value.schedule.due_at, value.mistake.id))

    def review_mistake(
        self,
        household_id: UUID,
        child_id: UUID,
        mistake_id: UUID,
        request: ReviewMistakeRequest,
        idempotency_key: str,
    ) -> tuple[MistakeWithSchedule, bool]:
        operation = f"review_mistake:{mistake_id}"
        fingerprint = _fingerprint(request)
        receipt_key = (household_id, operation, idempotency_key)
        existing = self._receipts.get(receipt_key)
        if existing is not None:
            if existing[0] != fingerprint:
                raise IdempotencyConflictError
            return self._records[existing[1]], True
        current = self._records.get(mistake_id)
        if current is None or current.mistake.child_id != child_id:
            raise LookupError
        now = datetime.now(UTC)
        outcome = _determine_review_outcome(request, None)
        interval = _next_interval(current.schedule.interval_days, outcome)
        resolved = outcome is ReviewOutcome.CORRECT and current.schedule.repetitions >= 2
        mistake = current.mistake.model_copy(
            update={
                "status": MistakeStatus.RESOLVED if resolved else MistakeStatus.OPEN,
                "resolved_at": now if resolved else None,
            }
        )
        schedule = current.schedule.model_copy(
            update={
                "due_at": now + timedelta(days=interval),
                "interval_days": interval,
                "repetitions": current.schedule.repetitions + 1
                if outcome is ReviewOutcome.CORRECT
                else 0,
                "last_outcome": outcome,
                "updated_at": now,
            }
        )
        result = MistakeWithSchedule(mistake=mistake, schedule=schedule)
        self._records[mistake_id] = result
        self._receipts[receipt_key] = (fingerprint, mistake_id)
        self._review_attempts.append(
            ReviewAttempt(
                id=uuid4(),
                household_id=household_id,
                child_id=child_id,
                mistake_id=mistake_id,
                verified_question_id=current.mistake.verified_question_id,
                answer_summary=request.answer_summary,
                submitted_answer=request.submitted_answer,
                evidence_confirmed=request.evidence_confirmed,
                outcome=outcome,
                policy_version=REVIEW_POLICY_VERSION
                if request.evidence_confirmed
                else "review-policy.legacy-compat",
                created_at=now,
            )
        )
        return result, False


def _fingerprint(value: BaseModel) -> str:
    return sha256(value.model_dump_json().encode()).hexdigest()


class PostgresMistakeRepository:
    def __init__(self, url: str | None = None) -> None:
        self._engine = create_engine(url or database_url(), pool_pre_ping=True)
        metadata = MetaData()
        self._mistakes = Table("mistake_records", metadata, autoload_with=self._engine)
        self._schedules = Table("review_schedules", metadata, autoload_with=self._engine)
        self._questions = Table("verified_questions", metadata, autoload_with=self._engine)
        self._sessions = Table("study_sessions", metadata, autoload_with=self._engine)
        self._idempotency = Table("idempotency_records", metadata, autoload_with=self._engine)
        self._audits = Table("audit_events", metadata, autoload_with=self._engine)
        self._attempts = Table("attempts", metadata, autoload_with=self._engine)
        self._review_attempts = Table("review_attempts", metadata, autoload_with=self._engine)

    @property
    def engine(self) -> Engine:
        return self._engine

    def close(self) -> None:
        self._engine.dispose()

    def _read(self, connection, mistake_id: UUID) -> MistakeWithSchedule:
        mistake_columns = tuple(
            column.label(f"mistake_{column.name}") for column in self._mistakes.columns
        )
        schedule_columns = tuple(
            column.label(f"schedule_{column.name}") for column in self._schedules.columns
        )
        row = (
            connection.execute(
                select(*mistake_columns, *schedule_columns)
                .select_from(
                    self._mistakes.join(
                        self._schedules, self._schedules.c.mistake_id == self._mistakes.c.id
                    )
                )
                .where(self._mistakes.c.id == mistake_id)
            )
            .mappings()
            .one()
        )
        mistake_values = {
            column.name: row[f"mistake_{column.name}"] for column in self._mistakes.columns
        }
        schedule_values = {
            column.name: row[f"schedule_{column.name}"] for column in self._schedules.columns
        }
        question_row = connection.execute(
            select(self._questions).where(
                self._questions.c.id == mistake_values["verified_question_id"],
                self._questions.c.household_id == mistake_values["household_id"],
                self._questions.c.child_id == mistake_values["child_id"],
            )
        ).mappings().one_or_none()
        question = None
        if question_row is not None:
            question = ReviewQuestion(
                id=question_row["id"],
                question_text=question_row["question_text"],
                options=tuple(question_row["options"]),
                formulas=tuple(question_row["formulas"]),
            )
        return MistakeWithSchedule(
            mistake=MistakeRecord.model_validate(mistake_values),
            schedule=ReviewSchedule.model_validate(schedule_values),
            question=question,
        )

    def create_mistake(
        self,
        household_id: UUID,
        child_id: UUID,
        request: CreateMistakeRequest,
        idempotency_key: str,
    ) -> tuple[MistakeWithSchedule, bool]:
        operation = f"create_mistake:{child_id}"
        fingerprint = _fingerprint(request)
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
                return self._read(connection, receipt["resource_id"]), True
            valid = connection.execute(
                select(self._questions.c.id)
                .join(self._sessions, self._sessions.c.child_id == self._questions.c.child_id)
                .where(
                    self._questions.c.id == request.verified_question_id,
                    self._questions.c.household_id == household_id,
                    self._questions.c.child_id == child_id,
                    self._sessions.c.id == request.session_id,
                    self._sessions.c.household_id == household_id,
                    self._sessions.c.child_id == child_id,
                )
            ).scalar_one_or_none()
            if valid is None:
                raise LookupError
            duplicate = connection.execute(
                select(self._mistakes.c.id).where(
                    self._mistakes.c.household_id == household_id,
                    self._mistakes.c.child_id == child_id,
                    self._mistakes.c.verified_question_id == request.verified_question_id,
                )
            ).scalar_one_or_none()
            if duplicate is not None:
                raise ValueError("mistake already exists")
            mistake_id, schedule_id = uuid4(), uuid4()
            connection.execute(
                insert(self._mistakes).values(
                    id=mistake_id,
                    household_id=household_id,
                    child_id=child_id,
                    verified_question_id=request.verified_question_id,
                    session_id=request.session_id,
                    reason=request.reason,
                    status=MistakeStatus.OPEN.value,
                    created_at=now,
                )
            )
            connection.execute(
                insert(self._schedules).values(
                    id=schedule_id,
                    household_id=household_id,
                    child_id=child_id,
                    mistake_id=mistake_id,
                    due_at=now + timedelta(days=1),
                    interval_days=1,
                    repetitions=0,
                    last_outcome=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            connection.execute(
                insert(self._idempotency).values(
                    household_id=household_id,
                    operation=operation,
                    idempotency_key=idempotency_key,
                    fingerprint=fingerprint,
                    resource_type="mistake_record",
                    resource_id=mistake_id,
                    created_at=now,
                )
            )
            connection.execute(
                insert(self._audits).values(
                    id=uuid4(),
                    household_id=household_id,
                    event_name="mistake_recorded",
                    resource_id=mistake_id,
                    recorded_at=now,
                )
            )
            return self._read(connection, mistake_id), False

    def closeout(
        self,
        household_id: UUID,
        child_id: UUID,
        request: MistakeCloseoutRequest,
        idempotency_key: str,
    ) -> tuple[MistakeCloseoutResult, bool]:
        """Complete a capture session and persist a qualifying mistake atomically."""

        operation = f"mistake_closeout:{request.session_id}"
        fingerprint = _fingerprint(request)
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
                replayed_mistake = (
                    self._read(connection, receipt["resource_id"])
                    if request.outcome == "needs_review"
                    else None
                )
                return MistakeCloseoutResult(
                    session_id=request.session_id, outcome=request.outcome, mistake=replayed_mistake
                ), True

            session = (
                connection.execute(
                    select(self._sessions)
                    .where(
                        self._sessions.c.id == request.session_id,
                        self._sessions.c.household_id == household_id,
                        self._sessions.c.child_id == child_id,
                        self._sessions.c.status == "active",
                    )
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            question = (
                connection.execute(
                    select(self._questions).where(
                        self._questions.c.id == request.verified_question_id,
                        self._questions.c.household_id == household_id,
                        self._questions.c.child_id == child_id,
                        self._questions.c.evidence_confirmed.is_(True),
                    )
                )
                .mappings()
                .one_or_none()
            )
            if session is None or question is None:
                raise LookupError
            evidence = connection.execute(
                select(self._attempts.c.id).where(
                    self._attempts.c.session_id == request.session_id,
                    self._attempts.c.household_id == household_id,
                    self._attempts.c.child_id == child_id,
                    self._attempts.c.evidence_confirmed.is_(True),
                    self._attempts.c.answer_state.in_(("worked", "blank")),
                )
            ).first()
            if evidence is None:
                raise ValueError("confirmed answer evidence is required")

            connection.execute(
                update(self._sessions)
                .where(self._sessions.c.id == request.session_id)
                .values(status="completed", completed_at=now, outcome=request.outcome)
            )
            mistake: MistakeWithSchedule | None = None
            resource_id = request.session_id
            if request.outcome == "needs_review":
                mistake_id = connection.execute(
                    select(self._mistakes.c.id).where(
                        self._mistakes.c.household_id == household_id,
                        self._mistakes.c.child_id == child_id,
                        self._mistakes.c.verified_question_id == request.verified_question_id,
                    )
                ).scalar_one_or_none()
                if mistake_id is None:
                    mistake_id, schedule_id = uuid4(), uuid4()
                    connection.execute(
                        insert(self._mistakes).values(
                            id=mistake_id,
                            household_id=household_id,
                            child_id=child_id,
                            verified_question_id=request.verified_question_id,
                            session_id=request.session_id,
                            reason=request.reason,
                            status=MistakeStatus.OPEN.value,
                            created_at=now,
                        )
                    )
                    connection.execute(
                        insert(self._schedules).values(
                            id=schedule_id,
                            household_id=household_id,
                            child_id=child_id,
                            mistake_id=mistake_id,
                            due_at=now + timedelta(days=1),
                            interval_days=1,
                            repetitions=0,
                            last_outcome=None,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                resource_id = mistake_id
                mistake = self._read(connection, mistake_id)
            connection.execute(
                insert(self._idempotency).values(
                    household_id=household_id,
                    operation=operation,
                    idempotency_key=idempotency_key,
                    fingerprint=fingerprint,
                    resource_type="mistake_closeout",
                    resource_id=resource_id,
                    created_at=now,
                )
            )
            connection.execute(
                insert(self._audits).values(
                    id=uuid4(),
                    household_id=household_id,
                    event_name="mistake_closeout",
                    resource_id=resource_id,
                    recorded_at=now,
                )
            )
            return MistakeCloseoutResult(
                session_id=request.session_id, outcome=request.outcome, mistake=mistake
            ), False

    def list_mistakes(
        self, household_id: UUID, child_id: UUID, due_before: datetime | None = None
    ) -> list[MistakeWithSchedule]:
        with self._engine.connect() as connection:
            query = (
                select(self._mistakes.c.id)
                .join(self._schedules, self._schedules.c.mistake_id == self._mistakes.c.id)
                .where(
                    self._mistakes.c.household_id == household_id,
                    self._mistakes.c.child_id == child_id,
                    self._mistakes.c.status == MistakeStatus.OPEN.value,
                )
                .order_by(self._schedules.c.due_at, self._mistakes.c.id)
            )
            if due_before is not None:
                query = query.where(self._schedules.c.due_at <= due_before)
            ids = connection.execute(query).scalars().all()
            return [self._read(connection, mistake_id) for mistake_id in ids]

    def review_mistake(
        self,
        household_id: UUID,
        child_id: UUID,
        mistake_id: UUID,
        request: ReviewMistakeRequest,
        idempotency_key: str,
    ) -> tuple[MistakeWithSchedule, bool]:
        operation = f"review_mistake:{mistake_id}"
        fingerprint = _fingerprint(request)
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
                return self._read(connection, receipt["resource_id"]), True
            current = (
                connection.execute(
                    select(self._mistakes, self._schedules)
                    .join(self._schedules, self._schedules.c.mistake_id == self._mistakes.c.id)
                    .where(
                        self._mistakes.c.id == mistake_id,
                        self._mistakes.c.household_id == household_id,
                        self._mistakes.c.child_id == child_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if current is None:
                raise LookupError
            repetitions = int(current["repetitions"])
            expected_answer = connection.execute(
                select(self._questions.c.answer_text).where(
                    self._questions.c.id == current["verified_question_id"],
                    self._questions.c.household_id == household_id,
                    self._questions.c.child_id == child_id,
                )
            ).scalar_one_or_none()
            outcome = _determine_review_outcome(request, expected_answer)
            interval = _next_interval(int(current["interval_days"]), outcome)
            resolved = outcome is ReviewOutcome.CORRECT and repetitions >= 2
            connection.execute(
                update(self._mistakes)
                .where(self._mistakes.c.id == mistake_id)
                .values(
                    status=MistakeStatus.RESOLVED.value if resolved else MistakeStatus.OPEN.value,
                    resolved_at=now if resolved else None,
                )
            )
            connection.execute(
                update(self._schedules)
                .where(self._schedules.c.mistake_id == mistake_id)
                .values(
                    due_at=now + timedelta(days=interval),
                    interval_days=interval,
                    repetitions=repetitions + 1 if outcome is ReviewOutcome.CORRECT else 0,
                    last_outcome=outcome.value,
                    updated_at=now,
                )
            )
            connection.execute(
                insert(self._review_attempts).values(
                    id=uuid4(),
                    household_id=household_id,
                    child_id=child_id,
                    mistake_id=mistake_id,
                    verified_question_id=current["verified_question_id"],
                    answer_summary=request.answer_summary,
                    submitted_answer=request.submitted_answer,
                    evidence_confirmed=request.evidence_confirmed,
                    outcome=outcome.value,
                    policy_version=(
                        REVIEW_POLICY_VERSION
                        if request.evidence_confirmed
                        else "review-policy.legacy-compat"
                    ),
                    created_at=now,
                )
            )
            connection.execute(
                insert(self._idempotency).values(
                    household_id=household_id,
                    operation=operation,
                    idempotency_key=idempotency_key,
                    fingerprint=fingerprint,
                    resource_type="review_schedule",
                    resource_id=mistake_id,
                    created_at=now,
                )
            )
            connection.execute(
                insert(self._audits).values(
                    id=uuid4(),
                    household_id=household_id,
                    event_name="mistake_reviewed",
                    resource_id=mistake_id,
                    recorded_at=now,
                )
            )
            return self._read(connection, mistake_id), False
