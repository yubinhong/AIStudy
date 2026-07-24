"""Read-only, privacy-minimized learning projections for parent reports."""

from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import MetaData, Table, create_engine, delete, func, insert, select
from sqlalchemy.engine import Engine, RowMapping

from study_api.database import database_url
from study_api.domain.mistake_repository import MistakeRecord, ReviewSchedule
from study_api.domain.models import Attempt, AuditEvent, ChildProfile, StudySession, StudyTask
from study_api.domain.repository import IdempotencyConflictError
from study_api.privacy_models import VerifiedQuestion
from study_api.tutor_policy import TutorHintResponse


class ReviewItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: UUID
    task_id: UUID
    task_title: str
    reason: str = "child_requested_review"


class WeeklyReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    child_id: UUID
    week_start: date
    week_end: date
    tasks_assigned: int = Field(ge=0)
    tasks_completed: int = Field(ge=0)
    tasks_skipped: int = Field(ge=0)
    sessions_completed: int = Field(ge=0)
    needs_review: int = Field(ge=0)
    verified_questions: int = Field(ge=0)
    tutor_turns: int = Field(ge=0)
    completion_rate: float = Field(ge=0, le=1)
    review_items: tuple[ReviewItem, ...]


class ChildDataExport(BaseModel):
    """Portable family data without credentials, object keys or image bytes."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = "child-data-export.v1"
    generated_at: datetime
    child: ChildProfile
    tasks: tuple[StudyTask, ...]
    sessions: tuple[StudySession, ...]
    attempts: tuple[Attempt, ...]
    verified_questions: tuple[VerifiedQuestion, ...]
    tutor_turns: tuple[TutorHintResponse, ...]
    mistakes: tuple[MistakeRecord, ...] = ()
    review_schedules: tuple[ReviewSchedule, ...] = ()


class LearningDetail(BaseModel):
    """Parent-visible trace for one confirmed question and its Tutor turns."""

    model_config = ConfigDict(frozen=True)

    question: VerifiedQuestion
    tutor_turns: tuple[TutorHintResponse, ...]


class InsightsRepository(Protocol):
    def weekly_report(
        self, household_id: UUID, child_id: UUID, week_start: date
    ) -> WeeklyReport: ...

    def export_child(
        self,
        household_id: UUID,
        child_id: UUID,
        idempotency_key: str,
    ) -> tuple[ChildDataExport, bool]: ...

    def learning_details(
        self, household_id: UUID, child_id: UUID, limit: int = 20
    ) -> tuple[LearningDetail, ...]: ...


class EmptyInsightsRepository:
    """Safe local fallback when PostgreSQL projections are not configured."""

    def weekly_report(self, household_id: UUID, child_id: UUID, week_start: date) -> WeeklyReport:
        del household_id
        return WeeklyReport(
            child_id=child_id,
            week_start=week_start,
            week_end=week_start + timedelta(days=6),
            tasks_assigned=0,
            tasks_completed=0,
            tasks_skipped=0,
            sessions_completed=0,
            needs_review=0,
            verified_questions=0,
            tutor_turns=0,
            completion_rate=0,
            review_items=(),
        )

    def export_child(
        self,
        household_id: UUID,
        child_id: UUID,
        idempotency_key: str,
    ) -> tuple[ChildDataExport, bool]:
        del household_id, child_id, idempotency_key
        raise LookupError

    def learning_details(
        self, household_id: UUID, child_id: UUID, limit: int = 20
    ) -> tuple[LearningDetail, ...]:
        del household_id, child_id, limit
        return ()


class PostgresInsightsRepository:
    def __init__(self, url: str | None = None) -> None:
        self._engine = create_engine(url or database_url(), pool_pre_ping=True)
        metadata = MetaData()
        self._tasks = Table("study_tasks", metadata, autoload_with=self._engine)
        self._children = Table("child_profiles", metadata, autoload_with=self._engine)
        self._sessions = Table("study_sessions", metadata, autoload_with=self._engine)
        self._attempts = Table("attempts", metadata, autoload_with=self._engine)
        self._captures = Table("captures", metadata, autoload_with=self._engine)
        self._verified_questions = Table("verified_questions", metadata, autoload_with=self._engine)
        self._tutor_turns = Table("tutor_turns", metadata, autoload_with=self._engine)
        self._exports = Table("child_data_exports", metadata, autoload_with=self._engine)
        self._mistakes = Table("mistake_records", metadata, autoload_with=self._engine)
        self._schedules = Table("review_schedules", metadata, autoload_with=self._engine)
        self._idempotency = Table("idempotency_records", metadata, autoload_with=self._engine)
        self._audits = Table("audit_events", metadata, autoload_with=self._engine)

    @property
    def engine(self) -> Engine:
        return self._engine

    def close(self) -> None:
        self._engine.dispose()

    def weekly_report(self, household_id: UUID, child_id: UUID, week_start: date) -> WeeklyReport:
        week_end = week_start + timedelta(days=6)
        task_scope = (
            self._tasks.c.household_id == household_id,
            self._tasks.c.child_id == child_id,
            self._tasks.c.scheduled_for >= week_start,
            self._tasks.c.scheduled_for <= week_end,
        )
        with self._engine.connect() as connection:
            task_rows = (
                connection.execute(
                    select(
                        self._tasks.c.id,
                        self._tasks.c.title,
                        self._tasks.c.status,
                    ).where(*task_scope)
                )
                .mappings()
                .all()
            )
            task_ids = [row["id"] for row in task_rows]
            if not task_ids:
                return EmptyInsightsRepository().weekly_report(household_id, child_id, week_start)
            session_rows = (
                connection.execute(
                    select(
                        self._sessions.c.id,
                        self._sessions.c.task_id,
                        self._sessions.c.status,
                        self._sessions.c.outcome,
                    ).where(
                        self._sessions.c.household_id == household_id,
                        self._sessions.c.child_id == child_id,
                        self._sessions.c.task_id.in_(task_ids),
                    )
                )
                .mappings()
                .all()
            )
            session_ids = [row["id"] for row in session_rows]
            verified_count = 0
            tutor_count = 0
            if session_ids:
                verified_count = (
                    connection.scalar(
                        select(func.count())
                        .select_from(
                            self._verified_questions.join(
                                self._captures,
                                self._verified_questions.c.capture_id == self._captures.c.id,
                            )
                        )
                        .where(
                            self._verified_questions.c.household_id == household_id,
                            self._verified_questions.c.child_id == child_id,
                            self._captures.c.session_id.in_(session_ids),
                        )
                    )
                    or 0
                )
                tutor_count = (
                    connection.scalar(
                        select(func.count())
                        .select_from(
                            self._tutor_turns.join(
                                self._verified_questions,
                                self._tutor_turns.c.verified_question_id
                                == self._verified_questions.c.id,
                            ).join(
                                self._captures,
                                self._verified_questions.c.capture_id == self._captures.c.id,
                            )
                        )
                        .where(
                            self._tutor_turns.c.household_id == household_id,
                            self._tutor_turns.c.child_id == child_id,
                            self._captures.c.session_id.in_(session_ids),
                        )
                    )
                    or 0
                )

        titles = {row["id"]: row["title"] for row in task_rows}
        review_items = tuple(
            ReviewItem(
                session_id=row["id"],
                task_id=row["task_id"],
                task_title=titles[row["task_id"]],
            )
            for row in session_rows
            if row["outcome"] == "needs_review"
        )
        completed_tasks = sum(row["status"] == "completed" for row in task_rows)
        skipped_tasks = sum(row["status"] == "skipped" for row in task_rows)
        finished_tasks = completed_tasks + skipped_tasks
        return WeeklyReport(
            child_id=child_id,
            week_start=week_start,
            week_end=week_end,
            tasks_assigned=len(task_rows),
            tasks_completed=completed_tasks,
            tasks_skipped=skipped_tasks,
            sessions_completed=sum(row["status"] == "completed" for row in session_rows),
            needs_review=len(review_items),
            verified_questions=int(verified_count),
            tutor_turns=int(tutor_count),
            completion_rate=finished_tasks / len(task_rows),
            review_items=review_items,
        )

    @staticmethod
    def _verified_question(row: RowMapping) -> VerifiedQuestion:
        payload = dict(row)
        payload["options"] = tuple(payload["options"])
        payload["formulas"] = tuple(payload["formulas"])
        payload["answer_steps"] = tuple(payload["answer_steps"])
        payload.pop("household_id", None)
        payload.pop("child_id", None)
        return VerifiedQuestion.model_validate(payload)

    @staticmethod
    def _tutor_turn(row: RowMapping) -> TutorHintResponse:
        payload = dict(row)
        payload["direct_answer"] = payload.pop("final_answer")
        payload["solution_steps"] = tuple(payload["solution_steps"])
        payload.pop("household_id", None)
        payload.pop("child_id", None)
        return TutorHintResponse.model_validate(payload)

    def learning_details(
        self, household_id: UUID, child_id: UUID, limit: int = 20
    ) -> tuple[LearningDetail, ...]:
        with self._engine.connect() as connection:
            question_rows = (
                connection.execute(
                    select(self._verified_questions)
                    .where(
                        self._verified_questions.c.household_id == household_id,
                        self._verified_questions.c.child_id == child_id,
                    )
                    .order_by(
                        self._verified_questions.c.verified_at.desc(),
                        self._verified_questions.c.id.desc(),
                    )
                    .limit(limit)
                )
                .mappings()
                .all()
            )
            question_ids = [row["id"] for row in question_rows]
            turn_rows = (
                connection.execute(
                    select(self._tutor_turns)
                    .where(
                        self._tutor_turns.c.household_id == household_id,
                        self._tutor_turns.c.child_id == child_id,
                        self._tutor_turns.c.verified_question_id.in_(question_ids),
                    )
                    .order_by(self._tutor_turns.c.created_at, self._tutor_turns.c.id)
                )
                .mappings()
                .all()
                if question_ids
                else []
            )
        turns_by_question: dict[UUID, list[TutorHintResponse]] = {}
        for row in turn_rows:
            turn = self._tutor_turn(row)
            turns_by_question.setdefault(turn.verified_question_id, []).append(turn)
        return tuple(
            LearningDetail(
                question=(question := self._verified_question(row)),
                tutor_turns=tuple(turns_by_question.get(question.id, ())),
            )
            for row in question_rows
        )

    def cleanup_expired_exports(self, now: datetime | None = None) -> int:
        effective_now = now or datetime.now(UTC)
        with self._engine.begin() as connection:
            expired_ids = list(
                connection.scalars(
                    select(self._exports.c.id).where(self._exports.c.expires_at <= effective_now)
                )
            )
            if not expired_ids:
                return 0
            connection.execute(
                delete(self._idempotency).where(
                    self._idempotency.c.resource_type == "child_data_export",
                    self._idempotency.c.resource_id.in_(expired_ids),
                )
            )
            connection.execute(delete(self._exports).where(self._exports.c.id.in_(expired_ids)))
            return len(expired_ids)

    def export_child(
        self,
        household_id: UUID,
        child_id: UUID,
        idempotency_key: str,
    ) -> tuple[ChildDataExport, bool]:
        operation = f"export_child:{child_id}"
        fingerprint = sha256(str(child_id).encode()).hexdigest()
        now = datetime.now(UTC)
        self.cleanup_expired_exports(now)
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
            if existing is not None and existing["fingerprint"] != fingerprint:
                raise IdempotencyConflictError
            if existing is not None:
                snapshot = connection.execute(
                    select(self._exports.c.payload).where(
                        self._exports.c.id == existing["resource_id"],
                        self._exports.c.household_id == household_id,
                        self._exports.c.child_id == child_id,
                    )
                ).scalar_one_or_none()
                if snapshot is None:
                    raise RuntimeError("child data export receipt has no snapshot")
                return ChildDataExport.model_validate(snapshot), True
            child_row = (
                connection.execute(
                    select(self._children).where(
                        self._children.c.household_id == household_id,
                        self._children.c.id == child_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if child_row is None:
                raise LookupError
            task_rows = (
                connection.execute(
                    select(self._tasks)
                    .where(
                        self._tasks.c.household_id == household_id,
                        self._tasks.c.child_id == child_id,
                    )
                    .order_by(self._tasks.c.created_at, self._tasks.c.id)
                )
                .mappings()
                .all()
            )
            session_rows = (
                connection.execute(
                    select(self._sessions)
                    .where(
                        self._sessions.c.household_id == household_id,
                        self._sessions.c.child_id == child_id,
                    )
                    .order_by(self._sessions.c.started_at, self._sessions.c.id)
                )
                .mappings()
                .all()
            )
            attempt_rows = (
                connection.execute(
                    select(self._attempts)
                    .where(
                        self._attempts.c.household_id == household_id,
                        self._attempts.c.child_id == child_id,
                    )
                    .order_by(self._attempts.c.recorded_at, self._attempts.c.id)
                )
                .mappings()
                .all()
            )
            verified_rows = (
                connection.execute(
                    select(self._verified_questions)
                    .where(
                        self._verified_questions.c.household_id == household_id,
                        self._verified_questions.c.child_id == child_id,
                    )
                    .order_by(
                        self._verified_questions.c.verified_at,
                        self._verified_questions.c.id,
                    )
                )
                .mappings()
                .all()
            )
            tutor_rows = (
                connection.execute(
                    select(self._tutor_turns)
                    .where(
                        self._tutor_turns.c.household_id == household_id,
                        self._tutor_turns.c.child_id == child_id,
                    )
                    .order_by(self._tutor_turns.c.created_at, self._tutor_turns.c.id)
                )
                .mappings()
                .all()
            )
            mistake_rows = (
                connection.execute(
                    select(self._mistakes)
                    .where(
                        self._mistakes.c.household_id == household_id,
                        self._mistakes.c.child_id == child_id,
                    )
                    .order_by(self._mistakes.c.created_at, self._mistakes.c.id)
                )
                .mappings()
                .all()
            )
            schedule_rows = (
                connection.execute(
                    select(self._schedules)
                    .where(
                        self._schedules.c.household_id == household_id,
                        self._schedules.c.child_id == child_id,
                    )
                    .order_by(self._schedules.c.created_at, self._schedules.c.id)
                )
                .mappings()
                .all()
            )
            child_payload = dict(child_row)
            child_payload["subjects"] = list(child_payload["subjects"])
            child_payload.pop("updated_at", None)
            verified = []
            for row in verified_rows:
                verified.append(self._verified_question(row))
            tutor_turns = tuple(
                self._tutor_turn(row)
                for row in tutor_rows
            )
            export = ChildDataExport(
                generated_at=now,
                child=ChildProfile.model_validate(child_payload),
                tasks=tuple(StudyTask.model_validate(dict(row)) for row in task_rows),
                sessions=tuple(StudySession.model_validate(dict(row)) for row in session_rows),
                attempts=tuple(Attempt.model_validate(dict(row)) for row in attempt_rows),
                verified_questions=tuple(verified),
                tutor_turns=tutor_turns,
                mistakes=tuple(MistakeRecord.model_validate(dict(row)) for row in mistake_rows),
                review_schedules=tuple(
                    ReviewSchedule.model_validate(dict(row)) for row in schedule_rows
                ),
            )
            export_id = uuid4()
            connection.execute(
                insert(self._exports).values(
                    id=export_id,
                    household_id=household_id,
                    child_id=child_id,
                    payload=export.model_dump(mode="json"),
                    created_at=now,
                    expires_at=now + timedelta(hours=24),
                )
            )
            connection.execute(
                insert(self._idempotency).values(
                    household_id=household_id,
                    operation=operation,
                    idempotency_key=idempotency_key,
                    fingerprint=fingerprint,
                    resource_type="child_data_export",
                    resource_id=export_id,
                    created_at=now,
                )
            )
            event = AuditEvent(
                id=uuid4(),
                household_id=household_id,
                event_name="data_exported",
                resource_id=child_id,
                recorded_at=now,
            )
            connection.execute(insert(self._audits).values(**event.model_dump()))
            return export, False
