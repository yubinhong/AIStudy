"""Parent-approved, source-bound learning-task recommendations."""

from datetime import UTC, date, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import MetaData, Table, create_engine, insert, select, update
from sqlalchemy.engine import Engine

from study_api.database import database_url
from study_api.domain.models import TaskExercise, TaskSourceType
from study_api.domain.repository import IdempotencyConflictError


class RecommendationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RecommendationDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class TaskRecommendation(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    household_id: UUID
    child_id: UUID
    source_type: TaskSourceType
    source_key: str = Field(min_length=1, max_length=160)
    mistake_id: UUID | None = None
    snapshot_id: UUID | None = None
    curriculum_chunk_id: UUID | None = None
    knowledge_point_id: UUID | None = None
    title: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=240)
    knowledge_point: str = Field(min_length=1, max_length=120)
    exercises: tuple[TaskExercise, ...] = Field(default=(), max_length=5)
    estimated_minutes: int = Field(ge=5, le=60)
    scheduled_for: date
    strategy_version: str = Field(min_length=1, max_length=80)
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=160)
    status: RecommendationStatus
    task_id: UUID | None = None
    created_at: datetime
    decided_at: datetime | None = None


class CreateRecommendationRequest(BaseModel):
    child_id: UUID


class RecommendationDraft(BaseModel):
    """A validated plan item whose exercises all point to known local sources."""

    source_type: TaskSourceType
    source_key: str = Field(min_length=1, max_length=160)
    mistake_id: UUID | None = None
    snapshot_id: UUID | None = None
    curriculum_chunk_id: UUID | None = None
    knowledge_point_id: UUID | None = None
    title: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=240)
    knowledge_point: str = Field(min_length=1, max_length=120)
    exercises: tuple[TaskExercise, ...] = Field(min_length=1, max_length=5)
    estimated_minutes: int = Field(ge=5, le=60)
    scheduled_for: date
    strategy_version: str = Field(min_length=1, max_length=80)
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=160)


class DecideRecommendationRequest(BaseModel):
    decision: RecommendationDecision


class TaskRecommendationRepository(Protocol):
    def generate(
        self,
        household_id: UUID,
        child_id: UUID,
        draft: RecommendationDraft,
        idempotency_key: str,
    ) -> tuple[TaskRecommendation, bool]: ...

    def list(
        self, household_id: UUID, child_id: UUID, pending_only: bool = False
    ) -> list[TaskRecommendation]: ...

    def decide(
        self,
        household_id: UUID,
        child_id: UUID,
        recommendation_id: UUID,
        request: DecideRecommendationRequest,
        idempotency_key: str,
    ) -> tuple[TaskRecommendation, bool]: ...

    def attach_task(
        self, household_id: UUID, recommendation_id: UUID, task_id: UUID
    ) -> TaskRecommendation: ...


def _fingerprint(value: BaseModel) -> str:
    return sha256(value.model_dump_json().encode()).hexdigest()


class InMemoryTaskRecommendationRepository:
    def __init__(self) -> None:
        self._values: dict[UUID, TaskRecommendation] = {}
        self._receipts: dict[tuple[UUID, str, str], tuple[str, UUID]] = {}

    def generate(
        self,
        household_id: UUID,
        child_id: UUID,
        draft: RecommendationDraft,
        idempotency_key: str,
    ) -> tuple[TaskRecommendation, bool]:
        operation = f"recommendation_generate:{child_id}"
        fingerprint = sha256(f"{child_id}:{draft.model_dump_json()}".encode()).hexdigest()
        key = (household_id, operation, idempotency_key)
        existing = self._receipts.get(key)
        if existing is not None:
            if existing[0] != fingerprint:
                raise IdempotencyConflictError
            return self._values[existing[1]], True
        for value in self._values.values():
            if (
                value.child_id == child_id
                and value.status is RecommendationStatus.PENDING
                and value.source_key == draft.source_key
                and value.scheduled_for == draft.scheduled_for
            ):
                self._receipts[key] = (fingerprint, value.id)
                return value, True
        recommendation = TaskRecommendation(
            id=uuid4(),
            household_id=household_id,
            child_id=child_id,
            **draft.model_dump(),
            status=RecommendationStatus.PENDING,
            created_at=datetime.now(UTC),
        )
        self._values[recommendation.id] = recommendation
        self._receipts[key] = (fingerprint, recommendation.id)
        return recommendation, False

    def list(
        self, household_id: UUID, child_id: UUID, pending_only: bool = False
    ) -> list[TaskRecommendation]:
        values = [
            value
            for value in self._values.values()
            if value.household_id == household_id
            and value.child_id == child_id
            and (not pending_only or value.status is RecommendationStatus.PENDING)
        ]
        return sorted(values, key=lambda value: (value.created_at, value.id), reverse=True)

    def decide(
        self,
        household_id: UUID,
        child_id: UUID,
        recommendation_id: UUID,
        request: DecideRecommendationRequest,
        idempotency_key: str,
    ) -> tuple[TaskRecommendation, bool]:
        operation = f"recommendation_decide:{recommendation_id}"
        fingerprint = _fingerprint(request)
        key = (household_id, operation, idempotency_key)
        existing = self._receipts.get(key)
        if existing is not None:
            if existing[0] != fingerprint:
                raise IdempotencyConflictError
            return self._values[existing[1]], True
        current = self._values.get(recommendation_id)
        if current is None or current.household_id != household_id or current.child_id != child_id:
            raise LookupError
        if current.status is not RecommendationStatus.PENDING:
            raise ValueError("recommendation has already been decided")
        decided = current.model_copy(
            update={
                "status": RecommendationStatus.APPROVED
                if request.decision is RecommendationDecision.APPROVE
                else RecommendationStatus.REJECTED,
                "decided_at": datetime.now(UTC),
            }
        )
        self._values[recommendation_id] = decided
        self._receipts[key] = (fingerprint, recommendation_id)
        return decided, False

    def attach_task(
        self, household_id: UUID, recommendation_id: UUID, task_id: UUID
    ) -> TaskRecommendation:
        current = self._values.get(recommendation_id)
        if current is None or current.household_id != household_id:
            raise LookupError
        updated = current.model_copy(update={"task_id": task_id})
        self._values[recommendation_id] = updated
        return updated


class PostgresTaskRecommendationRepository:
    def __init__(self, url: str | None = None) -> None:
        self._engine = create_engine(url or database_url(), pool_pre_ping=True)
        metadata = MetaData()
        self._recommendations = Table("task_recommendations", metadata, autoload_with=self._engine)
        self._idempotency = Table("idempotency_records", metadata, autoload_with=self._engine)

    @property
    def engine(self) -> Engine:
        return self._engine

    def close(self) -> None:
        self._engine.dispose()

    @staticmethod
    def _read(row: dict) -> TaskRecommendation:
        return TaskRecommendation.model_validate(row)

    def generate(
        self,
        household_id: UUID,
        child_id: UUID,
        draft: RecommendationDraft,
        idempotency_key: str,
    ) -> tuple[TaskRecommendation, bool]:
        operation = f"recommendation_generate:{child_id}"
        fingerprint = sha256(f"{child_id}:{draft.model_dump_json()}".encode()).hexdigest()
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
                row = (
                    connection.execute(
                        select(self._recommendations).where(
                            self._recommendations.c.id == receipt["resource_id"]
                        )
                    )
                    .mappings()
                    .one()
                )
                return self._read(dict(row)), True
            existing = (
                connection.execute(
                    select(self._recommendations).where(
                        self._recommendations.c.household_id == household_id,
                        self._recommendations.c.child_id == child_id,
                        self._recommendations.c.status == RecommendationStatus.PENDING.value,
                        self._recommendations.c.source_key == draft.source_key,
                        self._recommendations.c.scheduled_for == draft.scheduled_for,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if existing is not None:
                recommendation = self._read(dict(existing))
                connection.execute(
                    insert(self._idempotency).values(
                        household_id=household_id,
                        operation=operation,
                        idempotency_key=idempotency_key,
                        fingerprint=fingerprint,
                        resource_type="task_recommendation",
                        resource_id=recommendation.id,
                        created_at=now,
                    )
                )
                return recommendation, True
            recommendation = TaskRecommendation(
                id=uuid4(),
                household_id=household_id,
                child_id=child_id,
                **draft.model_dump(),
                status=RecommendationStatus.PENDING,
                created_at=now,
            )
            values = recommendation.model_dump(exclude={"exercises"})
            values["source_type"] = recommendation.source_type.value
            values["status"] = recommendation.status.value
            values["exercises"] = [
                exercise.model_dump(mode="json") for exercise in recommendation.exercises
            ]
            connection.execute(insert(self._recommendations).values(**values))
            connection.execute(
                insert(self._idempotency).values(
                    household_id=household_id,
                    operation=operation,
                    idempotency_key=idempotency_key,
                    fingerprint=fingerprint,
                    resource_type="task_recommendation",
                    resource_id=recommendation.id,
                    created_at=now,
                )
            )
            return recommendation, False

    def list(
        self, household_id: UUID, child_id: UUID, pending_only: bool = False
    ) -> list[TaskRecommendation]:
        statement = select(self._recommendations).where(
            self._recommendations.c.household_id == household_id,
            self._recommendations.c.child_id == child_id,
        )
        if pending_only:
            statement = statement.where(self._recommendations.c.status == "pending")
        statement = statement.order_by(
            self._recommendations.c.created_at.desc(), self._recommendations.c.id.desc()
        )
        with self._engine.connect() as connection:
            return [self._read(dict(row)) for row in connection.execute(statement).mappings()]

    def decide(
        self,
        household_id: UUID,
        child_id: UUID,
        recommendation_id: UUID,
        request: DecideRecommendationRequest,
        idempotency_key: str,
    ) -> tuple[TaskRecommendation, bool]:
        operation = f"recommendation_decide:{recommendation_id}"
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
                row = (
                    connection.execute(
                        select(self._recommendations).where(
                            self._recommendations.c.id == receipt["resource_id"]
                        )
                    )
                    .mappings()
                    .one()
                )
                return self._read(dict(row)), True
            current = (
                connection.execute(
                    select(self._recommendations)
                    .where(
                        self._recommendations.c.id == recommendation_id,
                        self._recommendations.c.household_id == household_id,
                        self._recommendations.c.child_id == child_id,
                    )
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if current is None:
                raise LookupError
            if current["status"] != "pending":
                raise ValueError("recommendation has already been decided")
            status_value = (
                "approved" if request.decision is RecommendationDecision.APPROVE else "rejected"
            )
            connection.execute(
                update(self._recommendations)
                .where(self._recommendations.c.id == recommendation_id)
                .values(status=status_value, decided_at=now)
            )
            connection.execute(
                insert(self._idempotency).values(
                    household_id=household_id,
                    operation=operation,
                    idempotency_key=idempotency_key,
                    fingerprint=fingerprint,
                    resource_type="task_recommendation",
                    resource_id=recommendation_id,
                    created_at=now,
                )
            )
            row = (
                connection.execute(
                    select(self._recommendations).where(
                        self._recommendations.c.id == recommendation_id
                    )
                )
                .mappings()
                .one()
            )
            return self._read(dict(row)), False

    def attach_task(
        self, household_id: UUID, recommendation_id: UUID, task_id: UUID
    ) -> TaskRecommendation:
        with self._engine.begin() as connection:
            connection.execute(
                update(self._recommendations)
                .where(
                    self._recommendations.c.id == recommendation_id,
                    self._recommendations.c.household_id == household_id,
                )
                .values(task_id=task_id)
            )
            row = (
                connection.execute(
                    select(self._recommendations).where(
                        self._recommendations.c.id == recommendation_id
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise LookupError
            return self._read(dict(row))
