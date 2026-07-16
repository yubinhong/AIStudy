"""Local/CI OCR job queue and one-shot dispatcher boundaries.

The queue deliberately stores identifiers, the explicit OCR mode, and stable
status only. It never stores object keys, image bytes, OCR text, or Provider
exception details.
Production durability can replace the queue implementation with the approved
Redis/worker boundary without changing the scheduling route or dispatcher.
"""

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import MetaData, Table, and_, create_engine, insert, or_, select, update
from sqlalchemy.engine import Engine, RowMapping

from study_api.database import database_url
from study_api.domain.models import OcrJobReceipt, OcrJobStatus, OcrMode, OcrResult


@dataclass(frozen=True)
class OcrJob:
    id: UUID
    household_id: UUID
    capture_id: UUID
    child_id: UUID
    idempotency_key: str
    mode: OcrMode
    status: OcrJobStatus
    attempt: int
    enqueued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result_id: UUID | None = None
    error_code: str | None = None

    def receipt(self) -> OcrJobReceipt:
        return OcrJobReceipt(
            id=self.id,
            capture_id=self.capture_id,
            mode=self.mode,
            status=self.status,
            attempt=self.attempt,
            enqueued_at=self.enqueued_at,
            started_at=self.started_at,
            finished_at=self.finished_at,
            result_id=self.result_id,
        )


class OcrJobStateError(RuntimeError):
    """Raised when a queue transition does not match the current state."""


class OcrJobIdempotencyConflictError(RuntimeError):
    """Raised when an idempotency key is reused with a different OCR mode."""


class OcrJobQueue(Protocol):
    def enqueue(
        self,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        idempotency_key: str,
        mode: OcrMode = OcrMode.TEXT,
    ) -> tuple[OcrJob, bool]: ...

    def claim_next(self) -> OcrJob | None: ...

    def complete(self, job_id: UUID, result_id: UUID) -> None: ...

    def fail(self, job_id: UUID) -> None: ...

    def get(self, job_id: UUID) -> OcrJob: ...


class InMemoryOcrJobQueue:
    """Deterministic local queue for API tests and a future worker adapter."""

    def __init__(self) -> None:
        self._jobs: dict[UUID, OcrJob] = {}
        self._idempotency: dict[tuple[UUID, UUID, str], UUID] = {}
        self._order: list[UUID] = []

    def enqueue(
        self,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        idempotency_key: str,
        mode: OcrMode = OcrMode.TEXT,
    ) -> tuple[OcrJob, bool]:
        key = (household_id, capture_id, idempotency_key)
        existing_id = self._idempotency.get(key)
        if existing_id is not None:
            existing = self._jobs[existing_id]
            if existing.mode is not mode:
                raise OcrJobIdempotencyConflictError
            return existing, True
        job = OcrJob(
            id=uuid4(),
            household_id=household_id,
            capture_id=capture_id,
            child_id=child_id,
            idempotency_key=idempotency_key,
            mode=mode,
            status=OcrJobStatus.QUEUED,
            attempt=0,
            enqueued_at=datetime.now(UTC),
        )
        self._jobs[job.id] = job
        self._idempotency[key] = job.id
        self._order.append(job.id)
        return job, False

    def claim_next(self) -> OcrJob | None:
        for job_id in self._order:
            job = self._jobs[job_id]
            if job.status is not OcrJobStatus.QUEUED:
                continue
            running = replace(
                job,
                status=OcrJobStatus.RUNNING,
                attempt=job.attempt + 1,
                started_at=datetime.now(UTC),
            )
            self._jobs[job_id] = running
            return running
        return None

    def complete(self, job_id: UUID, result_id: UUID) -> None:
        job = self._job(job_id)
        if job.status is not OcrJobStatus.RUNNING:
            raise OcrJobStateError
        self._jobs[job_id] = replace(
            job,
            status=OcrJobStatus.SUCCEEDED,
            finished_at=datetime.now(UTC),
            result_id=result_id,
        )

    def fail(self, job_id: UUID) -> None:
        job = self._job(job_id)
        if job.status is not OcrJobStatus.RUNNING:
            raise OcrJobStateError
        self._jobs[job_id] = replace(
            job,
            status=OcrJobStatus.FAILED,
            finished_at=datetime.now(UTC),
            error_code="ocr_job_failed",
        )

    def get(self, job_id: UUID) -> OcrJob:
        return self._job(job_id)

    def _job(self, job_id: UUID) -> OcrJob:
        try:
            return self._jobs[job_id]
        except KeyError as error:
            raise LookupError from error


class PostgresOcrJobQueue:
    """Durable queue ledger with row-locked claim and stale-lease recovery."""

    def __init__(self, url: str | None = None, *, lease_seconds: int = 600) -> None:
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        self._engine = create_engine(url or database_url(), pool_pre_ping=True)
        self._lease = timedelta(seconds=lease_seconds)
        metadata = MetaData()
        self._jobs = Table("ocr_jobs", metadata, autoload_with=self._engine)

    @property
    def engine(self) -> Engine:
        return self._engine

    def close(self) -> None:
        self._engine.dispose()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _job(row: RowMapping | dict[str, object]) -> OcrJob:
        return OcrJob(
            id=row["id"],  # type: ignore[arg-type]
            household_id=row["household_id"],  # type: ignore[arg-type]
            capture_id=row["capture_id"],  # type: ignore[arg-type]
            child_id=row["child_id"],  # type: ignore[arg-type]
            idempotency_key=str(row["idempotency_key"]),
            mode=OcrMode(str(row["mode"])),
            status=OcrJobStatus(str(row["status"])),
            attempt=int(row["attempt"]),  # type: ignore[arg-type]
            enqueued_at=row["enqueued_at"],  # type: ignore[arg-type]
            started_at=row["started_at"],  # type: ignore[arg-type]
            finished_at=row["finished_at"],  # type: ignore[arg-type]
            result_id=row["result_id"],  # type: ignore[arg-type]
            error_code=str(row["error_code"]) if row["error_code"] is not None else None,
        )

    def enqueue(
        self,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        idempotency_key: str,
        mode: OcrMode = OcrMode.TEXT,
    ) -> tuple[OcrJob, bool]:
        with self._engine.begin() as connection:
            existing = (
                connection.execute(
                    select(self._jobs).where(
                        self._jobs.c.household_id == household_id,
                        self._jobs.c.capture_id == capture_id,
                        self._jobs.c.idempotency_key == idempotency_key,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if existing is not None:
                existing_job = self._job(existing)
                if existing_job.mode is not mode:
                    raise OcrJobIdempotencyConflictError
                return existing_job, True
            job = OcrJob(
                id=uuid4(),
                household_id=household_id,
                capture_id=capture_id,
                child_id=child_id,
                idempotency_key=idempotency_key,
                mode=mode,
                status=OcrJobStatus.QUEUED,
                attempt=0,
                enqueued_at=self._now(),
            )
            connection.execute(insert(self._jobs).values(**job.__dict__))
            return job, False

    def claim_next(self) -> OcrJob | None:
        now = self._now()
        stale_before = now - self._lease
        claimable = or_(
            self._jobs.c.status == OcrJobStatus.QUEUED.value,
            and_(
                self._jobs.c.status == OcrJobStatus.RUNNING.value,
                self._jobs.c.started_at.is_not(None),
                self._jobs.c.started_at < stale_before,
            ),
        )
        with self._engine.begin() as connection:
            row = (
                connection.execute(
                    select(self._jobs)
                    .where(claimable)
                    .order_by(self._jobs.c.enqueued_at, self._jobs.c.id)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            updated = connection.execute(
                update(self._jobs)
                .where(self._jobs.c.id == row["id"], claimable)
                .values(
                    status=OcrJobStatus.RUNNING.value,
                    attempt=self._jobs.c.attempt + 1,
                    started_at=now,
                    error_code=None,
                )
            )
            if updated.rowcount != 1:
                raise OcrJobStateError
            payload = dict(row)
            payload.update(
                {
                    "status": OcrJobStatus.RUNNING.value,
                    "attempt": int(row["attempt"]) + 1,
                    "started_at": now,
                    "error_code": None,
                }
            )
            return self._job(payload)

    def complete(self, job_id: UUID, result_id: UUID) -> None:
        with self._engine.begin() as connection:
            updated = connection.execute(
                update(self._jobs)
                .where(
                    self._jobs.c.id == job_id,
                    self._jobs.c.status == OcrJobStatus.RUNNING.value,
                )
                .values(
                    status=OcrJobStatus.SUCCEEDED.value,
                    finished_at=self._now(),
                    result_id=result_id,
                    error_code=None,
                )
            )
            if updated.rowcount != 1:
                raise OcrJobStateError

    def fail(self, job_id: UUID) -> None:
        with self._engine.begin() as connection:
            updated = connection.execute(
                update(self._jobs)
                .where(
                    self._jobs.c.id == job_id,
                    self._jobs.c.status == OcrJobStatus.RUNNING.value,
                )
                .values(
                    status=OcrJobStatus.FAILED.value,
                    finished_at=self._now(),
                    error_code="ocr_job_failed",
                )
            )
            if updated.rowcount != 1:
                raise OcrJobStateError

    def get(self, job_id: UUID) -> OcrJob:
        with self._engine.connect() as connection:
            row = (
                connection.execute(select(self._jobs).where(self._jobs.c.id == job_id))
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise LookupError
            return self._job(row)


class OcrJobRunner(Protocol):
    def run(
        self,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        idempotency_key: str,
        mode: OcrMode = OcrMode.TEXT,
    ) -> tuple[OcrResult, bool]: ...


@dataclass(frozen=True)
class OcrDispatchResult:
    job_id: UUID
    status: OcrJobStatus
    result_id: UUID | None = None


class LocalOcrDispatcher:
    """Claim and execute at most one queued OCR job without leaking errors."""

    def __init__(self, queue: OcrJobQueue, runner: OcrJobRunner) -> None:
        self._queue = queue
        self._runner = runner

    def run_once(self) -> OcrDispatchResult | None:
        job = self._queue.claim_next()
        if job is None:
            return None
        try:
            result, _ = self._runner.run(
                job.household_id,
                job.capture_id,
                job.child_id,
                f"ocr-worker:{job.id}",
                mode=job.mode,
            )
        except Exception:  # noqa: BLE001 -- queue stores only a stable code.
            self._queue.fail(job.id)
            return OcrDispatchResult(job_id=job.id, status=OcrJobStatus.FAILED)
        self._queue.complete(job.id, result.id)
        return OcrDispatchResult(
            job_id=job.id,
            status=OcrJobStatus.SUCCEEDED,
            result_id=result.id,
        )
