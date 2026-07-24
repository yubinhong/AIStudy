"""Append-only persistence for Tutor hints created from verified questions."""

from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import MetaData, Table, create_engine, desc, insert, select
from sqlalchemy.engine import Engine, RowMapping

from study_api.database import database_url
from study_api.domain.repository import IdempotencyConflictError
from study_api.tutor_policy import CurriculumSource, TutorHintContent, TutorHintResponse


class TutorTurnRepository(Protocol):
    def latest_before_level(
        self, household_id: UUID, child_id: UUID, verified_question_id: UUID, level: int
    ) -> TutorHintResponse | None: ...

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

    def latest_before_level(
        self, household_id: UUID, child_id: UUID, verified_question_id: UUID, level: int
    ) -> TutorHintResponse | None:
        del household_id, child_id
        candidates = [
            turn
            for turn in self._turns.values()
            if turn.verified_question_id == verified_question_id and turn.level < level
        ]
        return max(candidates, key=lambda turn: turn.created_at, default=None)


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

    def latest_before_level(
        self, household_id: UUID, child_id: UUID, verified_question_id: UUID, level: int
    ) -> TutorHintResponse | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    select(self._turns)
                    .where(
                        self._turns.c.household_id == household_id,
                        self._turns.c.child_id == child_id,
                        self._turns.c.verified_question_id == verified_question_id,
                        self._turns.c.level < level,
                    )
                    .order_by(desc(self._turns.c.created_at))
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
        return self._turn(row) if row is not None else None

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
            mode=row["mode"],
            answer_state=row["answer_state"],
            prompt=row["prompt"],
            next_step=row["next_step"],
            requires_child_response=row["requires_child_response"],
            direct_answer=row["final_answer"],
            solution_steps=tuple(row["solution_steps"]),
            verification=row["verification"],
            cost_cents=row["cost_cents"],
            curriculum_sources=tuple(
                CurriculumSource.model_validate(item)
                for item in (row.get("curriculum_sources") or [])
            ),
            hint_goal=row.get("hint_goal") or "understand_the_question",
            builds_on_turn_id=row.get("builds_on_turn_id"),
            revealed_elements=tuple(row.get("revealed_elements") or []),
            child_action=row.get("child_action") or "用自己的话说出下一步。",
            answer_exposure=row.get("answer_exposure") or "none",
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
                    mode=turn.mode,
                    answer_state=turn.answer_state,
                    prompt=turn.prompt,
                    next_step=turn.next_step,
                    requires_child_response=turn.requires_child_response,
                    final_answer=turn.direct_answer,
                    solution_steps=list(turn.solution_steps),
                    verification=turn.verification,
                    cost_cents=turn.cost_cents,
                    curriculum_sources=[
                        item.model_dump(mode="json") for item in turn.curriculum_sources
                    ],
                    hint_goal=turn.hint_goal,
                    builds_on_turn_id=turn.builds_on_turn_id,
                    revealed_elements=list(turn.revealed_elements),
                    child_action=turn.child_action,
                    answer_exposure=turn.answer_exposure,
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
