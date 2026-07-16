"""Assembly and one-shot execution boundary for the local OCR Worker."""

import json
import os
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from study_api.domain.ocr_result_repository import PostgresOcrResultRepository
from study_api.domain.sql_capture_repository import PostgresCaptureRepository
from study_api.object_storage import ObjectStorageConfig, S3ObjectStorage
from study_api.ocr_jobs import LocalOcrDispatcher, OcrDispatchResult, PostgresOcrJobQueue
from study_api.ocr_provider import LocalPaddleOcrAdapter, PaddleModelPaths
from study_api.ocr_service import LocalOcrJob


class WorkerInstance(Protocol):
    def run_once(self) -> OcrDispatchResult | None: ...

    def close(self) -> None: ...


@dataclass
class LocalOcrWorker:
    """One local Worker process with explicit resource cleanup."""

    dispatcher: LocalOcrDispatcher
    _closeables: tuple[Callable[[], None], ...]

    def run_once(self) -> OcrDispatchResult | None:
        return self.dispatcher.run_once()

    def close(self) -> None:
        for closeable in self._closeables:
            closeable()


def build_local_worker() -> LocalOcrWorker:
    """Build a Worker from only local MinIO, PostgreSQL, and pre-provisioned models."""

    models = PaddleModelPaths.from_environment()
    models.validate()
    storage = S3ObjectStorage(ObjectStorageConfig.from_environment())
    captures = PostgresCaptureRepository()
    results = PostgresOcrResultRepository()
    queue = PostgresOcrJobQueue()
    adapter = LocalPaddleOcrAdapter(models)
    runner = LocalOcrJob(captures, storage, adapter, results)
    return LocalOcrWorker(
        dispatcher=LocalOcrDispatcher(queue, runner),
        _closeables=(queue.close, captures.close, results.close),
    )


WorkerStatus = Literal["idle", "succeeded", "failed", "startup_error", "worker_error"]


@dataclass(frozen=True)
class WorkerSummary:
    status: WorkerStatus
    exit_code: int


def run_worker_once(
    builder: Callable[[], WorkerInstance] = build_local_worker,
) -> WorkerSummary:
    """Execute one job and return only a stable, non-sensitive summary."""

    try:
        worker = builder()
    except Exception:  # noqa: BLE001 -- startup details must not reach CLI output.
        return WorkerSummary(status="startup_error", exit_code=2)
    try:
        outcome = worker.run_once()
    except Exception:  # noqa: BLE001 -- runtime details must not reach CLI output.
        return WorkerSummary(status="worker_error", exit_code=1)
    finally:
        worker.close()
    if outcome is None:
        return WorkerSummary(status="idle", exit_code=0)
    if outcome.status.value == "failed":
        return WorkerSummary(status="failed", exit_code=1)
    return WorkerSummary(status="succeeded", exit_code=0)


def run_worker_watch(
    builder: Callable[[], WorkerInstance] = build_local_worker,
    *,
    poll_interval: float = 2.0,
    max_iterations: int | None = None,
) -> WorkerSummary:
    """Keep one local Worker process alive and poll the durable queue.

    The bounded ``max_iterations`` hook is used only by tests. Production local
    runs stop with Ctrl-C and always close model/database resources.
    """

    if poll_interval < 0:
        raise ValueError("poll_interval must be non-negative")
    if max_iterations is not None and max_iterations < 1:
        raise ValueError("max_iterations must be positive")
    try:
        worker = builder()
    except Exception:  # noqa: BLE001 -- startup details must not reach CLI output.
        return WorkerSummary(status="startup_error", exit_code=2)

    latest = WorkerSummary(status="idle", exit_code=0)
    iterations = 0
    try:
        while max_iterations is None or iterations < max_iterations:
            try:
                outcome = worker.run_once()
            except Exception:  # noqa: BLE001 -- runtime details must not reach CLI output.
                return WorkerSummary(status="worker_error", exit_code=1)
            if outcome is not None:
                latest = WorkerSummary(
                    status="failed" if outcome.status.value == "failed" else "succeeded",
                    exit_code=1 if outcome.status.value == "failed" else 0,
                )
            iterations += 1
            if max_iterations is not None or outcome is not None:
                if max_iterations is not None and iterations >= max_iterations:
                    break
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        return latest
    finally:
        worker.close()
    return latest


def _poll_interval_from_environment() -> float:
    raw = os.environ.get("OCR_WORKER_POLL_INTERVAL_SECONDS", "2")
    try:
        value = float(raw)
    except ValueError as error:
        raise ValueError("OCR worker poll interval must be numeric") from error
    if not 0.5 <= value <= 60:
        raise ValueError("OCR worker poll interval must be between 0.5 and 60 seconds")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    effective_argv = tuple(sys.argv[1:] if argv is None else argv)
    watch = "--watch" in effective_argv
    if watch:
        try:
            summary = run_worker_watch(poll_interval=_poll_interval_from_environment())
        except ValueError:
            summary = WorkerSummary(status="startup_error", exit_code=2)
    else:
        summary = run_worker_once()
    print(json.dumps({"status": summary.status}, ensure_ascii=True))
    return summary.exit_code
