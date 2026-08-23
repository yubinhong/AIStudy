"""Synthetic Task/Session/Attempt store for local contract and policy tests.

This module deliberately models append and idempotency semantics before the
PostgreSQL repository replaces it in TASK-0005's persistence milestone.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from study_api.domain.models import (
    MAX_DAILY_TASKS,
    AnswerState,
    Attempt,
    AuditEvent,
    CompleteStudySessionRequest,
    CreateTaskRequest,
    RecordAttemptRequest,
    SessionOutcome,
    StartStudySessionRequest,
    StudySession,
    StudySessionStatus,
    StudyTask,
    Subject,
    SyncBatchRequest,
    SyncBatchResult,
    SyncEventResult,
    TaskStatus,
)
from study_api.domain.repository import IdempotencyConflictError, ProfileRepository


class ResourceVersionConflictError(Exception):
    """Raised when a session starts against an out-of-date task version."""


class ChildAssignmentError(Exception):
    """Raised when a child principal is not assigned to a task or session."""


class SessionAlreadyCompletedError(Exception):
    """Raised when a final session is completed again with another command."""


class TaskNotStartableError(Exception):
    """Raised when a task is already active or has reached a terminal state."""


class TaskNotScheduledError(Exception):
    """Raised when a child tries to start a future task."""


class TaskCapacityError(Exception):
    """Raised when a child already has the daily task capacity assigned."""


class SessionNotActiveError(Exception):
    """Raised when a revoked or otherwise closed session receives a write."""


class TaskNotRevocableError(Exception):
    """Raised when a terminal task cannot be revoked."""


class TaskProgressConflictError(Exception):
    """Raised when a client tries to skip an exercise in a task session."""


@dataclass(frozen=True)
class StoredResult:
    fingerprint: str
    value: StudyTask | StudySession | Attempt


class InMemoryLearningRepository:
    """Local/CI reference semantics, not the PostgreSQL source of truth."""

    def __init__(self, profiles: ProfileRepository) -> None:
        self._profiles = profiles
        self._tasks: dict[UUID, StudyTask] = {}
        self._sessions: dict[UUID, StudySession] = {}
        self._attempts: dict[UUID, list[Attempt]] = {}
        self._event_attempts: dict[UUID, Attempt] = {}
        self._idempotency: dict[tuple[UUID, str, str], StoredResult] = {}
        self._audits: list[AuditEvent] = []

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _fingerprint(value: str) -> str:
        return sha256(value.encode("utf-8")).hexdigest()

    def list_tasks(self, household_id: UUID, child_id: UUID | None = None) -> list[StudyTask]:
        return sorted(
            (
                task
                for task in self._tasks.values()
                if task.household_id == household_id
                and (child_id is None or task.child_id == child_id)
            ),
            key=lambda task: (task.scheduled_for, task.created_at, task.id),
        )

    def get_task(self, household_id: UUID, task_id: UUID) -> StudyTask | None:
        task = self._tasks.get(task_id)
        return task if task is not None and task.household_id == household_id else None

    def _assert_daily_capacity(
        self, household_id: UUID, child_id: UUID, scheduled_for: object
    ) -> None:
        assigned = sum(
            task.household_id == household_id
            and task.child_id == child_id
            and task.scheduled_for == scheduled_for
            and task.status is not TaskStatus.REVOKED
            for task in self._tasks.values()
        )
        if assigned >= MAX_DAILY_TASKS:
            raise TaskCapacityError("daily task capacity reached")

    def create_task(
        self, household_id: UUID, request: CreateTaskRequest, idempotency_key: str
    ) -> tuple[StudyTask, bool]:
        if self._profiles.get_child(household_id, request.child_id) is None:
            raise LookupError
        return self._write_once(
            household_id,
            "create_task",
            request.model_dump_json(),
            idempotency_key,
            lambda: self._new_task(household_id, request),
            self._tasks,
        )

    def _new_task(self, household_id: UUID, request: CreateTaskRequest) -> StudyTask:
        self._assert_daily_capacity(household_id, request.child_id, request.scheduled_for)
        return StudyTask(
            id=uuid4(),
            household_id=household_id,
            child_id=request.child_id,
            title=request.title,
            subject=request.subject,
            scheduled_for=request.scheduled_for,
            status=TaskStatus.ASSIGNED,
            version=1,
            created_at=self._now(),
            source_type=request.source_type,
            reason=request.reason,
            knowledge_point=request.knowledge_point,
            knowledge_point_id=request.knowledge_point_id,
            exercises=request.exercises,
            estimated_minutes=request.estimated_minutes,
        )

    def start_session(
        self,
        household_id: UUID,
        task_id: UUID,
        child_id: UUID,
        request: StartStudySessionRequest,
        idempotency_key: str,
    ) -> tuple[StudySession, bool]:
        task = self.get_task(household_id, task_id)
        if task is None:
            raise LookupError
        if task.child_id != child_id:
            raise ChildAssignmentError
        payload = request.model_dump_json()
        key = (household_id, f"start_session:{task_id}", idempotency_key)
        existing = self._idempotency.get(key)
        if existing is not None:
            if existing.fingerprint != self._fingerprint(payload):
                raise IdempotencyConflictError
            return self._as_session(existing.value), True
        if task.version != request.expected_task_version:
            raise ResourceVersionConflictError
        if task.status is not TaskStatus.ASSIGNED:
            raise TaskNotStartableError
        if task.scheduled_for > self._now().date():
            raise TaskNotScheduledError
        updated_task = task.model_copy(
            update={"status": TaskStatus.IN_PROGRESS, "version": task.version + 1}
        )
        self._tasks[task_id] = updated_task
        session = StudySession(
            id=uuid4(),
            household_id=household_id,
            child_id=child_id,
            task_id=task_id,
            task_version=updated_task.version,
            status=StudySessionStatus.ACTIVE,
            started_at=self._now(),
        )
        self._sessions[session.id] = session
        self._idempotency[key] = StoredResult(self._fingerprint(payload), session)
        self._audit(household_id, "study_session_started", session.id)
        return session, False

    def revoke_task(
        self, household_id: UUID, task_id: UUID, idempotency_key: str
    ) -> tuple[StudyTask, bool]:
        task = self.get_task(household_id, task_id)
        if task is None:
            raise LookupError
        key = (household_id, f"revoke_task:{task_id}", idempotency_key)
        existing = self._idempotency.get(key)
        payload = "revoke"
        if existing is not None:
            if existing.fingerprint != self._fingerprint(payload):
                raise IdempotencyConflictError
            return self._as_task(existing.value), True
        if task.status in {
            TaskStatus.COMPLETED,
            TaskStatus.SKIPPED,
            TaskStatus.REVOKED,
        }:
            raise TaskNotRevocableError
        revoked = task.model_copy(
            update={"status": TaskStatus.REVOKED, "version": task.version + 1}
        )
        self._tasks[task.id] = revoked
        now = self._now()
        for session_id, session in tuple(self._sessions.items()):
            if session.task_id == task.id and session.status is StudySessionStatus.ACTIVE:
                self._sessions[session_id] = session.model_copy(
                    update={
                        "status": StudySessionStatus.REVOKED,
                        "completed_at": now,
                        "outcome": SessionOutcome.REVOKED,
                    }
                )
        self._idempotency[key] = StoredResult(self._fingerprint(payload), revoked)
        self._audit(household_id, "study_task_revoked", task.id)
        return revoked, False

    def create_capture_session(
        self,
        household_id: UUID,
        child_id: UUID,
        idempotency_key: str,
    ) -> tuple[StudySession, bool]:
        """Create one child-owned ad-hoc math task and active capture session.

        The operation is deliberately atomic from the caller's perspective and
        idempotent so a mobile retry cannot create duplicate daily sessions.
        """

        if self._profiles.get_child(household_id, child_id) is None:
            raise LookupError
        payload = str(child_id)
        key = (household_id, f"create_capture_session:{child_id}", idempotency_key)
        existing = self._idempotency.get(key)
        if existing is not None:
            if existing.fingerprint != self._fingerprint(payload):
                raise IdempotencyConflictError
            return self._as_session(existing.value), True

        now = self._now()
        task = StudyTask(
            id=uuid4(),
            household_id=household_id,
            child_id=child_id,
            title="即时拍题",
            subject=Subject.MATH,
            scheduled_for=now.date(),
            status=TaskStatus.IN_PROGRESS,
            version=2,
            created_at=now,
        )
        session = StudySession(
            id=uuid4(),
            household_id=household_id,
            child_id=child_id,
            task_id=task.id,
            task_version=task.version,
            status=StudySessionStatus.ACTIVE,
            started_at=now,
        )
        self._tasks[task.id] = task
        self._sessions[session.id] = session
        self._idempotency[key] = StoredResult(self._fingerprint(payload), session)
        self._audit(household_id, "capture_task_created", task.id)
        self._audit(household_id, "capture_session_started", session.id)
        return session, False

    def get_session(self, household_id: UUID, session_id: UUID) -> StudySession | None:
        session = self._sessions.get(session_id)
        return session if session is not None and session.household_id == household_id else None

    def find_active_session(
        self, household_id: UUID, task_id: UUID, child_id: UUID
    ) -> StudySession | None:
        candidates = (
            session
            for session in self._sessions.values()
            if session.household_id == household_id
            and session.task_id == task_id
            and session.child_id == child_id
            and session.status is StudySessionStatus.ACTIVE
        )
        return max(candidates, key=lambda session: (session.started_at, session.id), default=None)

    def record_attempt(
        self,
        household_id: UUID,
        session_id: UUID,
        child_id: UUID,
        request: RecordAttemptRequest,
        idempotency_key: str,
    ) -> tuple[Attempt, bool]:
        session = self.get_session(household_id, session_id)
        if session is None:
            raise LookupError
        if session.child_id != child_id:
            raise ChildAssignmentError
        return self._append_attempt(
            household_id,
            session,
            request.event_id,
            request.answer_summary,
            request.answer_state,
            request.evidence_confirmed,
            request.next_exercise_index,
            idempotency_key,
        )

    def complete_session(
        self,
        household_id: UUID,
        session_id: UUID,
        child_id: UUID,
        request: CompleteStudySessionRequest,
        idempotency_key: str,
    ) -> tuple[StudySession, bool]:
        session = self.get_session(household_id, session_id)
        if session is None:
            raise LookupError
        if session.child_id != child_id:
            raise ChildAssignmentError
        payload = request.model_dump_json()
        key = (household_id, f"complete_session:{session_id}", idempotency_key)
        existing = self._idempotency.get(key)
        if existing is not None:
            if existing.fingerprint != self._fingerprint(payload):
                raise IdempotencyConflictError
            return self._as_session(existing.value), True
        if session.status is StudySessionStatus.COMPLETED:
            raise SessionAlreadyCompletedError
        if session.status is not StudySessionStatus.ACTIVE:
            raise SessionNotActiveError
        completed = session.model_copy(
            update={
                "status": StudySessionStatus.COMPLETED,
                "completed_at": self._now(),
                "outcome": request.outcome,
            }
        )
        task = self._tasks[session.task_id]
        task_status = (
            TaskStatus.SKIPPED if request.outcome.value == "skipped" else TaskStatus.COMPLETED
        )
        self._tasks[task.id] = task.model_copy(
            update={"status": task_status, "version": task.version + 1}
        )
        self._sessions[session.id] = completed
        self._idempotency[key] = StoredResult(self._fingerprint(payload), completed)
        self._audit(household_id, "study_session_completed", session.id)
        return completed, False

    def sync_attempts(
        self, household_id: UUID, child_id: UUID, request: SyncBatchRequest
    ) -> SyncBatchResult:
        prepared: list[tuple[StudySession, UUID, str, AnswerState, bool, int | None, str]] = []
        for event in request.events:
            session = self.get_session(household_id, event.session_id)
            if session is None:
                raise LookupError
            if session.child_id != child_id:
                raise ChildAssignmentError
            prepared.append(
                (
                    session,
                    event.event_id,
                    event.answer_summary,
                    event.answer_state,
                    event.evidence_confirmed,
                    event.next_exercise_index,
                    event.idempotency_key,
                )
            )
        self._preflight_attempts(household_id, prepared)
        results: list[SyncEventResult] = []
        for (
            session,
            event_id,
            answer_summary,
            answer_state,
            evidence_confirmed,
            next_exercise_index,
            idempotency_key,
        ) in prepared:
            attempt, replayed = self._append_attempt(
                household_id,
                session,
                event_id,
                answer_summary,
                answer_state,
                evidence_confirmed,
                next_exercise_index,
                idempotency_key,
            )
            results.append(
                SyncEventResult(
                    event_id=event_id, status="replayed" if replayed else "applied", attempt=attempt
                )
            )
        return SyncBatchResult(results=results)

    def _preflight_attempts(
        self,
        household_id: UUID,
        prepared: list[tuple[StudySession, UUID, str, AnswerState, bool, int | None, str]],
    ) -> None:
        seen_events: set[UUID] = set()
        for (
            session,
            event_id,
            answer_summary,
            answer_state,
            evidence_confirmed,
            next_exercise_index,
            idempotency_key,
        ) in prepared:
            if event_id in seen_events:
                raise IdempotencyConflictError
            seen_events.add(event_id)
            payload = (
                f"{session.id}:{event_id}:{answer_summary}:{answer_state}:"
                f"{evidence_confirmed}:{next_exercise_index}"
            )
            key = (household_id, f"record_attempt:{session.id}", idempotency_key)
            existing = self._idempotency.get(key)
            event_attempt = self._event_attempts.get(event_id)
            if existing is not None and existing.fingerprint != self._fingerprint(payload):
                raise IdempotencyConflictError
            if event_attempt is not None and (
                event_attempt.session_id != session.id
                or event_attempt.answer_summary != answer_summary
                or event_attempt.answer_state is not answer_state
                or event_attempt.evidence_confirmed != evidence_confirmed
            ):
                raise IdempotencyConflictError

    def _append_attempt(
        self,
        household_id: UUID,
        session: StudySession,
        event_id: UUID,
        answer_summary: str,
        answer_state: AnswerState,
        evidence_confirmed: bool,
        next_exercise_index: int | None,
        idempotency_key: str,
    ) -> tuple[Attempt, bool]:
        payload = (
            f"{session.id}:{event_id}:{answer_summary}:{answer_state}:"
            f"{evidence_confirmed}:{next_exercise_index}"
        )
        key = (household_id, f"record_attempt:{session.id}", idempotency_key)
        existing = self._idempotency.get(key)
        if existing is not None:
            if existing.fingerprint != self._fingerprint(payload):
                raise IdempotencyConflictError
            return self._as_attempt(existing.value), True
        event_attempt = self._event_attempts.get(event_id)
        if event_attempt is not None:
            if (
                event_attempt.session_id != session.id
                or event_attempt.answer_summary != answer_summary
            ):
                raise IdempotencyConflictError
            return event_attempt, True
        if session.status is not StudySessionStatus.ACTIVE:
            raise SessionNotActiveError
        self._advance_session_progress(session, next_exercise_index)
        sequence = len(self._attempts.setdefault(session.id, [])) + 1
        attempt = Attempt(
            id=uuid4(),
            event_id=event_id,
            household_id=household_id,
            child_id=session.child_id,
            session_id=session.id,
            sequence=sequence,
            answer_summary=answer_summary,
            answer_state=answer_state,
            evidence_confirmed=evidence_confirmed,
            recorded_at=self._now(),
        )
        self._attempts[session.id].append(attempt)
        self._event_attempts[event_id] = attempt
        self._idempotency[key] = StoredResult(self._fingerprint(payload), attempt)
        self._audit(household_id, "attempt_recorded", attempt.id)
        return attempt, False

    def _advance_session_progress(
        self, session: StudySession, next_exercise_index: int | None
    ) -> None:
        if next_exercise_index is None:
            return
        task = self._tasks.get(session.task_id)
        if task is None or not task.exercises:
            raise TaskProgressConflictError
        if next_exercise_index > len(task.exercises):
            raise TaskProgressConflictError
        current = self._sessions[session.id]
        if next_exercise_index > current.next_exercise_index + 1:
            raise TaskProgressConflictError
        if next_exercise_index > current.next_exercise_index:
            self._sessions[session.id] = current.model_copy(
                update={"next_exercise_index": next_exercise_index}
            )

    def _write_once(
        self,
        household_id: UUID,
        operation: str,
        payload: str,
        idempotency_key: str,
        factory: Callable[[], StudyTask],
        collection: dict[UUID, StudyTask],
    ) -> tuple[StudyTask, bool]:
        key = (household_id, operation, idempotency_key)
        existing = self._idempotency.get(key)
        if existing is not None:
            if existing.fingerprint != self._fingerprint(payload):
                raise IdempotencyConflictError
            return self._as_task(existing.value), True
        value = factory()
        collection[value.id] = value
        self._idempotency[key] = StoredResult(self._fingerprint(payload), value)
        self._audit(household_id, "task_created", value.id)
        return value, False

    def _audit(self, household_id: UUID, event_name: str, resource_id: UUID) -> None:
        self._audits.append(
            AuditEvent(
                id=uuid4(),
                household_id=household_id,
                event_name=event_name,
                resource_id=resource_id,
                recorded_at=self._now(),
            )
        )

    @staticmethod
    def _as_task(value: StudyTask | StudySession | Attempt) -> StudyTask:
        if not isinstance(value, StudyTask):
            raise TypeError("unexpected idempotency value")
        return value

    @staticmethod
    def _as_session(value: StudyTask | StudySession | Attempt) -> StudySession:
        if not isinstance(value, StudySession):
            raise TypeError("unexpected idempotency value")
        return value

    @staticmethod
    def _as_attempt(value: StudyTask | StudySession | Attempt) -> Attempt:
        if not isinstance(value, Attempt):
            raise TypeError("unexpected idempotency value")
        return value
