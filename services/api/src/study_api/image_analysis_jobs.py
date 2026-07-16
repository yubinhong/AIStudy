"""Provider-neutral ImageAnalysis job ledger.

This module records a user-confirmed sanitization receipt without touching image
bytes.  The local implementation intentionally stops at ``blocked`` while no
cloud Provider, terms, region, budget, and legal approval exist.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Literal, Protocol, cast
from uuid import UUID, uuid4

from sqlalchemy import MetaData, Table, and_, create_engine, insert, or_, select, update
from sqlalchemy.engine import Engine, RowMapping

from study_api.database import database_url
from study_api.domain.repository import IdempotencyConflictError
from study_api.privacy_models import (
    ImageAnalysisJobReceipt,
    ImageAnalysisJobStatus,
    StartImageAnalysisRequest,
)


class ImageAnalysisJobRepository(Protocol):
    def create(
        self,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        idempotency_key: str,
        request: StartImageAnalysisRequest,
        *,
        status: ImageAnalysisJobStatus,
        error_code: str | None,
    ) -> tuple[ImageAnalysisJobReceipt, bool]: ...

    def get(
        self, household_id: UUID, capture_id: UUID, child_id: UUID, job_id: UUID
    ) -> ImageAnalysisJobReceipt: ...

    def get_for_household(
        self, household_id: UUID, capture_id: UUID, job_id: UUID
    ) -> ImageAnalysisJobReceipt: ...

    def claim_next(self) -> "ImageAnalysisJob | None": ...

    def complete(self, job_id: UUID, extraction_id: UUID) -> None: ...

    def fail(self, job_id: UUID, error_code: str = "image_analysis_failed") -> None: ...


@dataclass(frozen=True)
class ImageAnalysisJob:
    """Internal worker payload; it is never returned by an HTTP route."""

    id: UUID
    household_id: UUID
    capture_id: UUID
    child_id: UUID
    idempotency_key: str
    status: ImageAnalysisJobStatus
    attempt: int
    sanitization_schema_version: Literal["privacy-sanitization.v1"]
    sanitized_derivative_sha256: str
    created_at: datetime
    updated_at: datetime
    extraction_id: UUID | None = None
    error_code: str | None = None

    def receipt(self) -> ImageAnalysisJobReceipt:
        return ImageAnalysisJobReceipt(
            id=self.id,
            capture_id=self.capture_id,
            household_id=self.household_id,
            child_id=self.child_id,
            status=self.status,
            attempt=self.attempt,
            sanitization_schema_version=self.sanitization_schema_version,
            sanitized_derivative_sha256=self.sanitized_derivative_sha256,
            created_at=self.created_at,
            updated_at=self.updated_at,
            extraction_id=self.extraction_id,
            error_code=self.error_code,
        )


def _fingerprint(request: StartImageAnalysisRequest) -> str:
    return sha256(request.model_dump_json().encode("utf-8")).hexdigest()


class InMemoryImageAnalysisJobRepository:
    """Deterministic local/CI ledger with no image or Provider state."""

    def __init__(self) -> None:
        self._jobs: dict[UUID, ImageAnalysisJobReceipt] = {}
        self._requests: dict[tuple[UUID, UUID, str], tuple[str, UUID]] = {}
        self._order: list[UUID] = []

    def create(
        self,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        idempotency_key: str,
        request: StartImageAnalysisRequest,
        *,
        status: ImageAnalysisJobStatus,
        error_code: str | None,
    ) -> tuple[ImageAnalysisJobReceipt, bool]:
        key = (household_id, capture_id, idempotency_key)
        fingerprint = _fingerprint(request)
        existing = self._requests.get(key)
        if existing is not None:
            if existing[0] != fingerprint:
                raise IdempotencyConflictError
            return self._jobs[existing[1]], True
        now = datetime.now(UTC)
        job = ImageAnalysisJobReceipt(
            id=uuid4(),
            capture_id=capture_id,
            household_id=household_id,
            child_id=child_id,
            status=status,
            attempt=0,
            sanitization_schema_version=request.sanitization.schema_version,
            sanitized_derivative_sha256=request.sanitization.sanitized_derivative_sha256,
            created_at=now,
            updated_at=now,
            error_code=error_code,
        )
        self._jobs[job.id] = job
        self._requests[key] = (fingerprint, job.id)
        if status is ImageAnalysisJobStatus.QUEUED:
            self._order.append(job.id)
        return job, False

    def get(
        self, household_id: UUID, capture_id: UUID, child_id: UUID, job_id: UUID
    ) -> ImageAnalysisJobReceipt:
        job = self._jobs.get(job_id)
        if (
            job is None
            or job.household_id != household_id
            or job.capture_id != capture_id
            or job.child_id != child_id
        ):
            raise LookupError
        return job

    def get_for_household(
        self, household_id: UUID, capture_id: UUID, job_id: UUID
    ) -> ImageAnalysisJobReceipt:
        job = self._jobs.get(job_id)
        if job is None or job.household_id != household_id or job.capture_id != capture_id:
            raise LookupError
        return job

    def claim_next(self) -> ImageAnalysisJob | None:
        for job_id in self._order:
            job = self._jobs[job_id]
            if job.status is not ImageAnalysisJobStatus.QUEUED:
                continue
            running = job.model_copy(
                update={
                    "status": ImageAnalysisJobStatus.RUNNING,
                    "attempt": job.attempt + 1,
                    "updated_at": datetime.now(UTC),
                    "error_code": None,
                }
            )
            self._jobs[job_id] = running
            return ImageAnalysisJob(
                id=running.id,
                household_id=running.household_id,
                capture_id=running.capture_id,
                child_id=running.child_id,
                idempotency_key=f"image-analysis-worker:{running.id}",
                status=running.status,
                attempt=running.attempt,
                sanitization_schema_version=running.sanitization_schema_version,
                sanitized_derivative_sha256=running.sanitized_derivative_sha256,
                created_at=running.created_at,
                updated_at=running.updated_at,
                extraction_id=running.extraction_id,
                error_code=running.error_code,
            )
        return None

    def complete(self, job_id: UUID, extraction_id: UUID) -> None:
        job = self._jobs.get(job_id)
        if job is None or job.status is not ImageAnalysisJobStatus.RUNNING:
            raise LookupError
        self._jobs[job_id] = job.model_copy(
            update={
                "status": ImageAnalysisJobStatus.SUCCEEDED,
                "updated_at": datetime.now(UTC),
                "extraction_id": extraction_id,
                "error_code": None,
            }
        )

    def fail(self, job_id: UUID, error_code: str = "image_analysis_failed") -> None:
        job = self._jobs.get(job_id)
        if job is None or job.status is not ImageAnalysisJobStatus.RUNNING:
            raise LookupError
        self._jobs[job_id] = job.model_copy(
            update={
                "status": ImageAnalysisJobStatus.FAILED,
                "updated_at": datetime.now(UTC),
                "error_code": error_code,
            }
        )


class PostgresImageAnalysisJobRepository:
    """PostgreSQL ledger for the provider-neutral job boundary."""

    def __init__(self, url: str | None = None, *, lease_seconds: int = 600) -> None:
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        self._engine = create_engine(url or database_url(), pool_pre_ping=True)
        self._lease = timedelta(seconds=lease_seconds)
        metadata = MetaData()
        self._jobs = Table("image_analysis_jobs", metadata, autoload_with=self._engine)

    @property
    def engine(self) -> Engine:
        return self._engine

    def close(self) -> None:
        self._engine.dispose()

    @staticmethod
    def _job(row: RowMapping) -> ImageAnalysisJobReceipt:
        return ImageAnalysisJobReceipt.model_validate(dict(row))

    @staticmethod
    def _work(row: RowMapping | dict[str, object]) -> ImageAnalysisJob:
        return ImageAnalysisJob(
            id=row["id"],  # type: ignore[arg-type]
            household_id=row["household_id"],  # type: ignore[arg-type]
            capture_id=row["capture_id"],  # type: ignore[arg-type]
            child_id=row["child_id"],  # type: ignore[arg-type]
            idempotency_key=str(row["idempotency_key"]),
            status=ImageAnalysisJobStatus(str(row["status"])),
            attempt=int(row["attempt"]),  # type: ignore[arg-type]
            sanitization_schema_version=cast(
                Literal["privacy-sanitization.v1"], str(row["sanitization_schema_version"])
            ),
            sanitized_derivative_sha256=str(row["sanitized_derivative_sha256"]),
            created_at=row["created_at"],  # type: ignore[arg-type]
            updated_at=row["updated_at"],  # type: ignore[arg-type]
            extraction_id=row["extraction_id"],  # type: ignore[arg-type]
            error_code=str(row["error_code"]) if row["error_code"] is not None else None,
        )

    def create(
        self,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        idempotency_key: str,
        request: StartImageAnalysisRequest,
        *,
        status: ImageAnalysisJobStatus,
        error_code: str | None,
    ) -> tuple[ImageAnalysisJobReceipt, bool]:
        fingerprint = _fingerprint(request)
        now = datetime.now(UTC)
        job = ImageAnalysisJobReceipt(
            id=uuid4(),
            capture_id=capture_id,
            household_id=household_id,
            child_id=child_id,
            status=status,
            attempt=0,
            sanitization_schema_version=request.sanitization.schema_version,
            sanitized_derivative_sha256=request.sanitization.sanitized_derivative_sha256,
            created_at=now,
            updated_at=now,
            error_code=error_code,
        )
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
                .first()
            )
            if existing is not None:
                if existing["request_fingerprint"] != fingerprint:
                    raise IdempotencyConflictError
                return self._job(existing), True
            connection.execute(
                insert(self._jobs).values(
                    **job.model_dump(),
                    idempotency_key=idempotency_key,
                    request_fingerprint=fingerprint,
                )
            )
        return job, False

    def get(
        self, household_id: UUID, capture_id: UUID, child_id: UUID, job_id: UUID
    ) -> ImageAnalysisJobReceipt:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    select(self._jobs).where(
                        self._jobs.c.id == job_id,
                        self._jobs.c.household_id == household_id,
                        self._jobs.c.capture_id == capture_id,
                        self._jobs.c.child_id == child_id,
                    )
                )
                .mappings()
                .first()
            )
        if row is None:
            raise LookupError
        return self._job(row)

    def get_for_household(
        self, household_id: UUID, capture_id: UUID, job_id: UUID
    ) -> ImageAnalysisJobReceipt:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    select(self._jobs).where(
                        self._jobs.c.id == job_id,
                        self._jobs.c.household_id == household_id,
                        self._jobs.c.capture_id == capture_id,
                    )
                )
                .mappings()
                .first()
            )
        if row is None:
            raise LookupError
        return self._job(row)

    def claim_next(self) -> ImageAnalysisJob | None:
        now = datetime.now(UTC)
        stale_before = now - self._lease
        claimable = or_(
            self._jobs.c.status == ImageAnalysisJobStatus.QUEUED.value,
            and_(
                self._jobs.c.status == ImageAnalysisJobStatus.RUNNING.value,
                self._jobs.c.updated_at < stale_before,
            ),
        )
        with self._engine.begin() as connection:
            row = (
                connection.execute(
                    select(self._jobs)
                    .where(claimable)
                    .order_by(self._jobs.c.created_at, self._jobs.c.id)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            attempt = int(row["attempt"]) + 1
            updated = connection.execute(
                update(self._jobs)
                .where(self._jobs.c.id == row["id"], claimable)
                .values(
                    status=ImageAnalysisJobStatus.RUNNING.value,
                    attempt=attempt,
                    updated_at=now,
                    error_code=None,
                )
            )
            if updated.rowcount != 1:
                raise RuntimeError("image analysis job claim conflict")
            payload = dict(row)
            payload.update(
                {
                    "status": ImageAnalysisJobStatus.RUNNING.value,
                    "attempt": attempt,
                    "updated_at": now,
                    "error_code": None,
                }
            )
            return self._work(payload)

    def complete(self, job_id: UUID, extraction_id: UUID) -> None:
        with self._engine.begin() as connection:
            updated = connection.execute(
                update(self._jobs)
                .where(
                    self._jobs.c.id == job_id,
                    self._jobs.c.status == ImageAnalysisJobStatus.RUNNING.value,
                )
                .values(
                    status=ImageAnalysisJobStatus.SUCCEEDED.value,
                    updated_at=datetime.now(UTC),
                    extraction_id=extraction_id,
                    error_code=None,
                )
            )
            if updated.rowcount != 1:
                raise RuntimeError("image analysis job completion conflict")

    def fail(self, job_id: UUID, error_code: str = "image_analysis_failed") -> None:
        if not 1 <= len(error_code) <= 64 or not error_code.isascii():
            raise ValueError("invalid image analysis error code")
        with self._engine.begin() as connection:
            updated = connection.execute(
                update(self._jobs)
                .where(
                    self._jobs.c.id == job_id,
                    self._jobs.c.status == ImageAnalysisJobStatus.RUNNING.value,
                )
                .values(
                    status=ImageAnalysisJobStatus.FAILED.value,
                    updated_at=datetime.now(UTC),
                    error_code=error_code,
                )
            )
            if updated.rowcount != 1:
                raise RuntimeError("image analysis job failure conflict")
