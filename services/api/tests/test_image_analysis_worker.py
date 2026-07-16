from uuid import UUID, uuid4

from study_api.image_analysis_jobs import InMemoryImageAnalysisJobRepository
from study_api.image_analysis_worker import ImageAnalysisDispatcher, build_worker, run_worker_watch
from study_api.privacy_models import ImageAnalysisJobStatus, StartImageAnalysisRequest


def _request() -> StartImageAnalysisRequest:
    return StartImageAnalysisRequest(
        expected_capture_version=1,
        sanitization={
            "sanitizer_version": "synthetic-v1",
            "safe_to_upload": True,
            "sensitive_types": [],
            "region_count": 0,
            "face_detected": False,
            "qr_detected": False,
            "barcode_detected": False,
            "blocked_reasons": [],
            "sanitized_derivative_sha256": "b" * 64,
        },
    )


class FakeRunner:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def run(self, _job) -> UUID:
        if self.fail:
            raise RuntimeError("provider details must stay private")
        return uuid4()


def test_dispatcher_completes_a_claimed_job_without_provider_details() -> None:
    jobs = InMemoryImageAnalysisJobRepository()
    job, _ = jobs.create(
        uuid4(),
        uuid4(),
        uuid4(),
        "image-analysis-worker-idempotency",
        _request(),
        status=ImageAnalysisJobStatus.QUEUED,
        error_code=None,
    )
    dispatcher = ImageAnalysisDispatcher(jobs, FakeRunner())

    result = dispatcher.run_once()

    assert result is not None
    assert result.status == "succeeded"
    assert result.extraction_id is not None
    assert (
        jobs.get(job.household_id, job.capture_id, job.child_id, job.id).status
        is ImageAnalysisJobStatus.SUCCEEDED
    )


def test_dispatcher_marks_provider_failure_with_stable_state() -> None:
    jobs = InMemoryImageAnalysisJobRepository()
    job, _ = jobs.create(
        uuid4(),
        uuid4(),
        uuid4(),
        "image-analysis-worker-failure",
        _request(),
        status=ImageAnalysisJobStatus.QUEUED,
        error_code=None,
    )
    result = ImageAnalysisDispatcher(jobs, FakeRunner(fail=True)).run_once()

    assert result is not None
    assert result.status == "failed"
    receipt = jobs.get(job.household_id, job.capture_id, job.child_id, job.id)
    assert receipt.status is ImageAnalysisJobStatus.FAILED
    assert receipt.error_code == "image_analysis_failed"


def test_disabled_provider_keeps_default_worker_idle(monkeypatch) -> None:
    monkeypatch.setenv("STUDY_NEWAPI_ENABLED", "false")

    summary = run_worker_watch(build_worker, poll_interval=0, max_iterations=2)

    assert summary.status == "idle"
    assert summary.exit_code == 0
