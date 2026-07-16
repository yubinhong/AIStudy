"""Durable worker for confirmed sanitized-image analysis via NewAPI."""

import json
import os
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from study_api.capture_media import read_safe_capture
from study_api.domain.capture_repository import CaptureRepository
from study_api.domain.question_extraction_repository import (
    PostgresQuestionExtractionRepository,
    QuestionExtractionRepository,
)
from study_api.domain.sql_capture_repository import PostgresCaptureRepository
from study_api.image_analysis_jobs import (
    ImageAnalysisJob,
    ImageAnalysisJobRepository,
    PostgresImageAnalysisJobRepository,
)
from study_api.newapi_provider import NewApiConfig, NewApiVisionProvider
from study_api.object_storage import ObjectStorageConfig, S3ObjectStorage


class ImageAnalysisRunner(Protocol):
    def run(self, job: ImageAnalysisJob) -> UUID: ...


class NewApiImageAnalysisRunner:
    """Read one private derivative, validate it, call NewAPI, and persist only schema data."""

    def __init__(
        self,
        captures: CaptureRepository,
        storage: S3ObjectStorage,
        provider: NewApiVisionProvider,
        extractions: QuestionExtractionRepository,
    ) -> None:
        self._captures = captures
        self._storage = storage
        self._provider = provider
        self._extractions = extractions

    def run(self, job: ImageAnalysisJob) -> UUID:
        pending = self._captures.get_capture_upload(job.household_id, job.capture_id, job.child_id)
        safe_capture = read_safe_capture(
            self._storage,
            pending.object_key,
            pending.capture.media_type,
            pending.capture.byte_size,
            pending.capture.content_sha256,
        )
        extraction = self._provider.analyze_sanitized_image(
            safe_capture.data,
            pending.capture.media_type,
            sanitization_schema=job.sanitization_schema_version,
        )
        record, _ = self._extractions.create(
            job.id,
            job.household_id,
            job.capture_id,
            job.child_id,
            extraction,
        )
        return record.id


@dataclass(frozen=True)
class ImageAnalysisDispatchResult:
    job_id: UUID
    status: Literal["succeeded", "failed"]
    extraction_id: UUID | None = None


class ImageAnalysisDispatcher:
    """Claim and execute at most one job while keeping failure details private."""

    def __init__(self, jobs: ImageAnalysisJobRepository, runner: ImageAnalysisRunner) -> None:
        self._jobs = jobs
        self._runner = runner

    def run_once(self) -> ImageAnalysisDispatchResult | None:
        job = self._jobs.claim_next()
        if job is None:
            return None
        try:
            extraction_id = self._runner.run(job)
        except Exception:  # noqa: BLE001 -- durable queue stores only a stable code.
            self._jobs.fail(job.id)
            return ImageAnalysisDispatchResult(job.id, "failed")
        self._jobs.complete(job.id, extraction_id)
        return ImageAnalysisDispatchResult(job.id, "succeeded", extraction_id)


class WorkerInstance(Protocol):
    def run_once(self) -> ImageAnalysisDispatchResult | None: ...

    def close(self) -> None: ...


@dataclass
class NewApiImageAnalysisWorker:
    dispatcher: ImageAnalysisDispatcher
    _closeables: tuple[Callable[[], None], ...]

    def run_once(self) -> ImageAnalysisDispatchResult | None:
        return self.dispatcher.run_once()

    def close(self) -> None:
        for closeable in self._closeables:
            closeable()


@dataclass
class DisabledImageAnalysisWorker:
    """Keep the default Compose worker healthy without reading or sending images."""

    def run_once(self) -> ImageAnalysisDispatchResult | None:
        return None

    def close(self) -> None:
        return None


def build_worker() -> WorkerInstance:
    config = NewApiConfig.from_environment()
    if not config.enabled:
        return DisabledImageAnalysisWorker()
    jobs = PostgresImageAnalysisJobRepository()
    captures = PostgresCaptureRepository()
    extractions = PostgresQuestionExtractionRepository()
    storage = S3ObjectStorage(ObjectStorageConfig.from_environment())
    provider = NewApiVisionProvider(config)
    runner = NewApiImageAnalysisRunner(captures, storage, provider, extractions)
    return NewApiImageAnalysisWorker(
        ImageAnalysisDispatcher(jobs, runner),
        (jobs.close, captures.close, extractions.close),
    )


WorkerStatus = Literal["idle", "succeeded", "failed", "startup_error", "worker_error"]


@dataclass(frozen=True)
class WorkerSummary:
    status: WorkerStatus
    exit_code: int


def run_worker_once(builder: Callable[[], WorkerInstance] = build_worker) -> WorkerSummary:
    try:
        worker = builder()
    except Exception:  # noqa: BLE001 -- CLI must not expose secrets or Provider details.
        return WorkerSummary("startup_error", 2)
    try:
        outcome = worker.run_once()
    except Exception:  # noqa: BLE001 -- CLI must not expose image/provider details.
        return WorkerSummary("worker_error", 1)
    finally:
        worker.close()
    if outcome is None:
        return WorkerSummary("idle", 0)
    return WorkerSummary(
        "succeeded" if outcome.status == "succeeded" else "failed",
        0 if outcome.status == "succeeded" else 1,
    )


def run_worker_watch(
    builder: Callable[[], WorkerInstance] = build_worker,
    *,
    poll_interval: float = 2.0,
    max_iterations: int | None = None,
) -> WorkerSummary:
    if poll_interval < 0 or (max_iterations is not None and max_iterations < 1):
        raise ValueError("invalid worker polling configuration")
    try:
        worker = builder()
    except Exception:  # noqa: BLE001
        return WorkerSummary("startup_error", 2)
    latest = WorkerSummary("idle", 0)
    iterations = 0
    try:
        while max_iterations is None or iterations < max_iterations:
            try:
                outcome = worker.run_once()
            except Exception:  # noqa: BLE001
                return WorkerSummary("worker_error", 1)
            if outcome is not None:
                latest = WorkerSummary(
                    "succeeded" if outcome.status == "succeeded" else "failed",
                    0 if outcome.status == "succeeded" else 1,
                )
            iterations += 1
            if max_iterations is not None and iterations >= max_iterations:
                break
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        return latest
    finally:
        worker.close()
    return latest


def _poll_interval() -> float:
    value = float(os.environ.get("IMAGE_ANALYSIS_WORKER_POLL_INTERVAL_SECONDS", "2"))
    if not 0.5 <= value <= 60:
        raise ValueError("image analysis worker poll interval must be between 0.5 and 60 seconds")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    args = tuple(sys.argv[1:] if argv is None else argv)
    try:
        summary = (
            run_worker_watch(poll_interval=_poll_interval())
            if "--watch" in args
            else run_worker_once()
        )
    except ValueError:
        summary = WorkerSummary("startup_error", 2)
    print(json.dumps({"status": summary.status}, ensure_ascii=True))
    return summary.exit_code
