"""PostgreSQL implementation of the learning repository.

The repository mirrors the local reference semantics while making attempt,
audit, idempotency and task-version writes transactional.
"""

from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import MetaData, Table, create_engine, func, insert, select, update
from sqlalchemy.engine import Connection, Engine, RowMapping

from study_api.database import database_url
from study_api.domain.learning_repository import (
    ChildAssignmentError,
    ResourceVersionConflictError,
)
from study_api.domain.models import (
    Attempt,
    AuditEvent,
    CreateTaskRequest,
    RecordAttemptRequest,
    StartStudySessionRequest,
    StudySession,
    StudySessionStatus,
    StudyTask,
    SyncBatchRequest,
    SyncBatchResult,
    SyncEventResult,
    TaskStatus,
)
from study_api.domain.repository import IdempotencyConflictError, InMemoryProfileRepository


class LearningRepository(Protocol):
    def list_tasks(self, household_id: UUID, child_id: UUID | None = None) -> list[StudyTask]: ...

    def create_task(
        self, household_id: UUID, request: CreateTaskRequest, idempotency_key: str
    ) -> tuple[StudyTask, bool]: ...

    def start_session(
        self,
        household_id: UUID,
        task_id: UUID,
        child_id: UUID,
        request: StartStudySessionRequest,
        idempotency_key: str,
    ) -> tuple[StudySession, bool]: ...

    def get_session(self, household_id: UUID, session_id: UUID) -> StudySession | None: ...

    def record_attempt(
        self,
        household_id: UUID,
        session_id: UUID,
        child_id: UUID,
        request: RecordAttemptRequest,
        idempotency_key: str,
    ) -> tuple[Attempt, bool]: ...

    def sync_attempts(
        self, household_id: UUID, child_id: UUID, request: SyncBatchRequest
    ) -> SyncBatchResult: ...


class PostgresLearningRepository:
    """PostgreSQL learning facts; schema is managed exclusively by Alembic."""

    def __init__(self, profiles: InMemoryProfileRepository, url: str | None = None) -> None:
        self._profiles = profiles
        self._engine = create_engine(url or database_url(), pool_pre_ping=True)
        metadata = MetaData()
        self._tasks = Table("study_tasks", metadata, autoload_with=self._engine)
        self._sessions = Table("study_sessions", metadata, autoload_with=self._engine)
        self._attempts = Table("attempts", metadata, autoload_with=self._engine)
        self._idempotency = Table("idempotency_records", metadata, autoload_with=self._engine)
        self._audits = Table("audit_events", metadata, autoload_with=self._engine)

    @property
    def engine(self) -> Engine:
        return self._engine

    def close(self) -> None:
        self._engine.dispose()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _fingerprint(value: str) -> str:
        return sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _task(row: RowMapping) -> StudyTask:
        return StudyTask.model_validate(dict(row))

    @staticmethod
    def _session(row: RowMapping) -> StudySession:
        return StudySession.model_validate(dict(row))

    @staticmethod
    def _attempt(row: RowMapping) -> Attempt:
        return Attempt.model_validate(dict(row))

    def list_tasks(self, household_id: UUID, child_id: UUID | None = None) -> list[StudyTask]:
        statement = select(self._tasks).where(self._tasks.c.household_id == household_id)
        if child_id is not None:
            statement = statement.where(self._tasks.c.child_id == child_id)
        statement = statement.order_by(
            self._tasks.c.scheduled_for, self._tasks.c.created_at, self._tasks.c.id
        )
        with self._engine.connect() as connection:
            return [self._task(row) for row in connection.execute(statement).mappings()]

    def get_session(self, household_id: UUID, session_id: UUID) -> StudySession | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    select(self._sessions).where(
                        self._sessions.c.id == session_id,
                        self._sessions.c.household_id == household_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
        return self._session(row) if row is not None else None

    def create_task(
        self, household_id: UUID, request: CreateTaskRequest, idempotency_key: str
    ) -> tuple[StudyTask, bool]:
        if self._profiles.get_child(household_id, request.child_id) is None:
            raise LookupError
        payload = request.model_dump_json()
        with self._engine.begin() as connection:
            existing = self._idempotency_result(
                connection, household_id, "create_task", idempotency_key
            )
            if existing is not None:
                return self._replay_task(connection, existing, payload)
            task = StudyTask(
                id=uuid4(),
                household_id=household_id,
                child_id=request.child_id,
                title=request.title,
                subject=request.subject,
                scheduled_for=request.scheduled_for,
                status=TaskStatus.ASSIGNED,
                version=1,
                created_at=self._now(),
            )
            connection.execute(insert(self._tasks).values(**task.model_dump()))
            self._store_idempotency(
                connection, household_id, "create_task", idempotency_key, payload, "task", task.id
            )
            self._audit(connection, household_id, "task_created", task.id)
            return task, False

    def start_session(
        self,
        household_id: UUID,
        task_id: UUID,
        child_id: UUID,
        request: StartStudySessionRequest,
        idempotency_key: str,
    ) -> tuple[StudySession, bool]:
        payload = request.model_dump_json()
        operation = f"start_session:{task_id}"
        with self._engine.begin() as connection:
            existing = self._idempotency_result(
                connection, household_id, operation, idempotency_key
            )
            if existing is not None:
                return self._replay_session(connection, existing, payload)
            row = (
                connection.execute(
                    select(self._tasks)
                    .where(self._tasks.c.id == task_id, self._tasks.c.household_id == household_id)
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise LookupError
            task = self._task(row)
            if task.child_id != child_id:
                raise ChildAssignmentError
            if task.version != request.expected_task_version:
                raise ResourceVersionConflictError
            task_version = task.version + 1
            connection.execute(
                update(self._tasks)
                .where(self._tasks.c.id == task_id, self._tasks.c.version == task.version)
                .values(status=TaskStatus.IN_PROGRESS.value, version=task_version)
            )
            session = StudySession(
                id=uuid4(),
                household_id=household_id,
                child_id=child_id,
                task_id=task_id,
                task_version=task_version,
                status=StudySessionStatus.ACTIVE,
                started_at=self._now(),
            )
            connection.execute(insert(self._sessions).values(**session.model_dump()))
            self._store_idempotency(
                connection, household_id, operation, idempotency_key, payload, "session", session.id
            )
            self._audit(connection, household_id, "study_session_started", session.id)
            return session, False

    def record_attempt(
        self,
        household_id: UUID,
        session_id: UUID,
        child_id: UUID,
        request: RecordAttemptRequest,
        idempotency_key: str,
    ) -> tuple[Attempt, bool]:
        with self._engine.begin() as connection:
            return self._append_attempt(
                connection,
                household_id,
                session_id,
                child_id,
                request.event_id,
                request.answer_summary,
                idempotency_key,
            )

    def sync_attempts(
        self, household_id: UUID, child_id: UUID, request: SyncBatchRequest
    ) -> SyncBatchResult:
        with self._engine.begin() as connection:
            seen_events: set[UUID] = set()
            for event in request.events:
                if event.event_id in seen_events:
                    raise IdempotencyConflictError
                seen_events.add(event.event_id)
                self._preflight_attempt(
                    connection,
                    household_id,
                    event.session_id,
                    child_id,
                    event.event_id,
                    event.answer_summary,
                    event.idempotency_key,
                )
            results: list[SyncEventResult] = []
            for event in request.events:
                attempt, replayed = self._append_attempt(
                    connection,
                    household_id,
                    event.session_id,
                    child_id,
                    event.event_id,
                    event.answer_summary,
                    event.idempotency_key,
                )
                results.append(
                    SyncEventResult(
                        event_id=event.event_id,
                        status="replayed" if replayed else "applied",
                        attempt=attempt,
                    )
                )
            return SyncBatchResult(results=results)

    def _append_attempt(
        self,
        connection: Connection,
        household_id: UUID,
        session_id: UUID,
        child_id: UUID,
        event_id: UUID,
        answer_summary: str,
        idempotency_key: str,
    ) -> tuple[Attempt, bool]:
        self._preflight_attempt(
            connection,
            household_id,
            session_id,
            child_id,
            event_id,
            answer_summary,
            idempotency_key,
        )
        operation = f"record_attempt:{session_id}"
        existing = self._idempotency_result(connection, household_id, operation, idempotency_key)
        if existing is not None:
            return self._replay_attempt(
                connection, existing, f"{session_id}:{event_id}:{answer_summary}"
            )
        event_row = (
            connection.execute(select(self._attempts).where(self._attempts.c.event_id == event_id))
            .mappings()
            .one_or_none()
        )
        if event_row is not None:
            attempt = self._attempt(event_row)
            self._store_idempotency(
                connection,
                household_id,
                operation,
                idempotency_key,
                f"{session_id}:{event_id}:{answer_summary}",
                "attempt",
                attempt.id,
            )
            return attempt, True
        session = self._session_for_child(connection, household_id, session_id, child_id)
        sequence = (
            connection.execute(
                select(func.coalesce(func.max(self._attempts.c.sequence), 0)).where(
                    self._attempts.c.session_id == session.id
                )
            ).scalar_one()
            + 1
        )
        attempt = Attempt(
            id=uuid4(),
            event_id=event_id,
            household_id=household_id,
            child_id=child_id,
            session_id=session_id,
            sequence=sequence,
            answer_summary=answer_summary,
            recorded_at=self._now(),
        )
        connection.execute(insert(self._attempts).values(**attempt.model_dump()))
        payload = f"{session_id}:{event_id}:{answer_summary}"
        self._store_idempotency(
            connection, household_id, operation, idempotency_key, payload, "attempt", attempt.id
        )
        self._audit(connection, household_id, "attempt_recorded", attempt.id)
        return attempt, False

    def _preflight_attempt(
        self,
        connection: Connection,
        household_id: UUID,
        session_id: UUID,
        child_id: UUID,
        event_id: UUID,
        answer_summary: str,
        idempotency_key: str,
    ) -> None:
        self._session_for_child(connection, household_id, session_id, child_id)
        payload = f"{session_id}:{event_id}:{answer_summary}"
        existing = self._idempotency_result(
            connection, household_id, f"record_attempt:{session_id}", idempotency_key
        )
        if existing is not None and existing["fingerprint"] != self._fingerprint(payload):
            raise IdempotencyConflictError
        event_row = (
            connection.execute(select(self._attempts).where(self._attempts.c.event_id == event_id))
            .mappings()
            .one_or_none()
        )
        if event_row is not None:
            attempt = self._attempt(event_row)
            if attempt.session_id != session_id or attempt.answer_summary != answer_summary:
                raise IdempotencyConflictError

    def _session_for_child(
        self, connection: Connection, household_id: UUID, session_id: UUID, child_id: UUID
    ) -> StudySession:
        row = (
            connection.execute(
                select(self._sessions)
                .where(
                    self._sessions.c.id == session_id, self._sessions.c.household_id == household_id
                )
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise LookupError
        session = self._session(row)
        if session.child_id != child_id:
            raise ChildAssignmentError
        return session

    def _idempotency_result(
        self, connection: Connection, household_id: UUID, operation: str, key: str
    ) -> RowMapping | None:
        return (
            connection.execute(
                select(self._idempotency).where(
                    self._idempotency.c.household_id == household_id,
                    self._idempotency.c.operation == operation,
                    self._idempotency.c.idempotency_key == key,
                )
            )
            .mappings()
            .one_or_none()
        )

    def _store_idempotency(
        self,
        connection: Connection,
        household_id: UUID,
        operation: str,
        key: str,
        payload: str,
        resource_type: str,
        resource_id: UUID,
    ) -> None:
        connection.execute(
            insert(self._idempotency).values(
                household_id=household_id,
                operation=operation,
                idempotency_key=key,
                fingerprint=self._fingerprint(payload),
                resource_type=resource_type,
                resource_id=resource_id,
                created_at=self._now(),
            )
        )

    def _audit(
        self, connection: Connection, household_id: UUID, event_name: str, resource_id: UUID
    ) -> None:
        event = AuditEvent(
            id=uuid4(),
            household_id=household_id,
            event_name=event_name,
            resource_id=resource_id,
            recorded_at=self._now(),
        )
        connection.execute(insert(self._audits).values(**event.model_dump()))

    def _replay_task(
        self, connection: Connection, record: RowMapping, payload: str
    ) -> tuple[StudyTask, bool]:
        if record["fingerprint"] != self._fingerprint(payload) or record["resource_type"] != "task":
            raise IdempotencyConflictError
        row = (
            connection.execute(select(self._tasks).where(self._tasks.c.id == record["resource_id"]))
            .mappings()
            .one()
        )
        return self._task(row), True

    def _replay_session(
        self, connection: Connection, record: RowMapping, payload: str
    ) -> tuple[StudySession, bool]:
        if (
            record["fingerprint"] != self._fingerprint(payload)
            or record["resource_type"] != "session"
        ):
            raise IdempotencyConflictError
        row = (
            connection.execute(
                select(self._sessions).where(self._sessions.c.id == record["resource_id"])
            )
            .mappings()
            .one()
        )
        return self._session(row), True

    def _replay_attempt(
        self, connection: Connection, record: RowMapping, payload: str
    ) -> tuple[Attempt, bool]:
        if (
            record["fingerprint"] != self._fingerprint(payload)
            or record["resource_type"] != "attempt"
        ):
            raise IdempotencyConflictError
        row = (
            connection.execute(
                select(self._attempts).where(self._attempts.c.id == record["resource_id"])
            )
            .mappings()
            .one()
        )
        return self._attempt(row), True
