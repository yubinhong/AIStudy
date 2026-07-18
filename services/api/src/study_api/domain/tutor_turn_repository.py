"""Append-only persistence for Tutor hints created from verified questions."""

from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import MetaData, Table, create_engine, insert, select
from sqlalchemy.engine import Engine, RowMapping

from study_api.database import database_url
from study_api.domain.repository import IdempotencyConflictError
from study_api.tutor_policy import TutorHintContent, TutorHintResponse


class TutorTurnRepository(Protocol):
    def create(
        self,
        household_id: UUID,
        child_id: UUID,
        verified_question_id: UUID,
        content: TutorHintContent,
        idempotency_key: str,
    ) -> tuple[TutorHintResponse, bool]: ...


def _fingerprint(verified_question_id: UUID, content: TutorHintContent) -> str:
    payload = f"{verified_question_id}:{content.model_dump_json()}"
    return sha256(payload.encode()).hexdigest()


class InMemoryTutorTurnRepository:
    def __init__(self) -> None:
        self._turns: dict[UUID, TutorHintResponse] = {}
        self._idempotency: dict[tuple[UUID, str, str], tuple[str, UUID]] = {}

    def create(
        self,
        household_id: UUID,
        child_id: UUID,
        verified_question_id: UUID,
        content: TutorHintContent,
        idempotency_key: str,
    ) -> tuple[TutorHintResponse, bool]:
        operation = f"tutor_hint:{verified_question_id}:{content.level}"
        key = (household_id, operation, idempotency_key)
        fingerprint = _fingerprint(verified_question_id, content)
        existing = self._idempotency.get(key)
        if existing is not None:
            if existing[0] != fingerprint:
                raise IdempotencyConflictError
            return self._turns[existing[1]], True
        turn = TutorHintResponse(
            **content.model_dump(),
            id=uuid4(),
            verified_question_id=verified_question_id,
            created_at=datetime.now(UTC),
        )
        self._turns[turn.id] = turn
        self._idempotency[key] = (fingerprint, turn.id)
        return turn, False


class PostgresTutorTurnRepository:
    def __init__(self, url: str | None = None) -> None:
        self._engine = create_engine(url or database_url(), pool_pre_ping=True)
        metadata = MetaData()
        self._turns = Table("tutor_turns", metadata, autoload_with=self._engine)
        self._idempotency = Table("idempotency_records", metadata, autoload_with=self._engine)

    @property
    def engine(self) -> Engine:
        return self._engine

    def close(self) -> None:
        self._engine.dispose()

    @staticmethod
    def _turn(row: RowMapping) -> TutorHintResponse:
        return TutorHintResponse(
            id=row["id"],
            verified_question_id=row["verified_question_id"],
            created_at=row["created_at"],
            level=row["level"],
            policy_version=row["policy_version"],
            provider=row["provider"],
            model=row["model"],
            prompt=row["prompt"],
            next_step=row["next_step"],
            cost_cents=row["cost_cents"],
        )

    def create(
        self,
        household_id: UUID,
        child_id: UUID,
        verified_question_id: UUID,
        content: TutorHintContent,
        idempotency_key: str,
    ) -> tuple[TutorHintResponse, bool]:
        operation = f"tutor_hint:{verified_question_id}:{content.level}"
        fingerprint = _fingerprint(verified_question_id, content)
        with self._engine.begin() as connection:
            existing = (
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
            if existing is not None:
                if existing["fingerprint"] != fingerprint:
                    raise IdempotencyConflictError
                row = (
                    connection.execute(
                        select(self._turns).where(
                            self._turns.c.id == existing["resource_id"],
                            self._turns.c.household_id == household_id,
                            self._turns.c.child_id == child_id,
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None:
                    raise LookupError
                return self._turn(row), True

            turn = TutorHintResponse(
                **content.model_dump(),
                id=uuid4(),
                verified_question_id=verified_question_id,
                created_at=datetime.now(UTC),
            )
            connection.execute(
                insert(self._turns).values(
                    id=turn.id,
                    household_id=household_id,
                    child_id=child_id,
                    verified_question_id=verified_question_id,
                    level=turn.level,
                    policy_version=turn.policy_version,
                    provider=turn.provider,
                    model=turn.model,
                    prompt=turn.prompt,
                    next_step=turn.next_step,
                    cost_cents=turn.cost_cents,
                    created_at=turn.created_at,
                )
            )
            connection.execute(
                insert(self._idempotency).values(
                    household_id=household_id,
                    operation=operation,
                    idempotency_key=idempotency_key,
                    fingerprint=fingerprint,
                    resource_type="tutor_turn",
                    resource_id=turn.id,
                    created_at=turn.created_at,
                )
            )
            return turn, False
