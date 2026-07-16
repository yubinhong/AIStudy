from uuid import uuid4

from study_api.domain.models import OcrJobStatus
from study_api.ocr_jobs import OcrDispatchResult
from study_api.ocr_worker import WorkerSummary, run_worker_once


class FakeWorker:
    def __init__(self, outcome: OcrDispatchResult | None = None, error: bool = False) -> None:
        self.outcome = outcome
        self.error = error
        self.closed = False

    def run_once(self) -> OcrDispatchResult | None:
        if self.error:
            raise RuntimeError("synthetic provider details")
        return self.outcome

    def close(self) -> None:
        self.closed = True


class SequenceWorker:
    def __init__(self, outcomes: list[OcrDispatchResult | None]) -> None:
        self.outcomes = outcomes
        self.closed = False

    def run_once(self) -> OcrDispatchResult | None:
        return self.outcomes.pop(0) if self.outcomes else None

    def close(self) -> None:
        self.closed = True


def _outcome(status: OcrJobStatus) -> OcrDispatchResult:
    return OcrDispatchResult(job_id=uuid4(), status=status, result_id=uuid4())


def test_worker_entrypoint_reports_idle_without_sensitive_details() -> None:
    worker = FakeWorker()

    summary = run_worker_once(lambda: worker)

    assert summary == WorkerSummary(status="idle", exit_code=0)
    assert worker.closed is True


def test_worker_entrypoint_reports_success_and_failure_stably() -> None:
    success = run_worker_once(lambda: FakeWorker(_outcome(OcrJobStatus.SUCCEEDED)))
    failure = run_worker_once(lambda: FakeWorker(_outcome(OcrJobStatus.FAILED)))

    assert success == WorkerSummary(status="succeeded", exit_code=0)
    assert failure == WorkerSummary(status="failed", exit_code=1)


def test_worker_entrypoint_hides_startup_and_runtime_errors() -> None:
    def fail_builder() -> FakeWorker:
        raise RuntimeError("secret config")

    startup = run_worker_once(fail_builder)
    runtime = run_worker_once(lambda: FakeWorker(error=True))

    assert startup == WorkerSummary(status="startup_error", exit_code=2)
    assert runtime == WorkerSummary(status="worker_error", exit_code=1)


def test_worker_watch_polls_a_durable_queue_and_closes_resources() -> None:
    worker = SequenceWorker([None, _outcome(OcrJobStatus.SUCCEEDED)])

    from study_api.ocr_worker import run_worker_watch

    summary = run_worker_watch(lambda: worker, poll_interval=0, max_iterations=2)

    assert summary == WorkerSummary(status="succeeded", exit_code=0)
    assert worker.closed is True
