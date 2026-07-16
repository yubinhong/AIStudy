from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from PIL import Image

from study_api.domain.capture_repository import PendingCaptureUpload
from study_api.domain.models import Capture, CaptureStatus
from study_api.domain.question_extraction_repository import InMemoryQuestionExtractionRepository
from study_api.image_analysis_jobs import InMemoryImageAnalysisJobRepository
from study_api.image_analysis_worker import (
    ImageAnalysisDispatcher,
    NewApiImageAnalysisRunner,
    build_worker,
    run_worker_watch,
)
from study_api.newapi_provider import NewApiProviderError
from study_api.privacy_models import (
    ImageAnalysisJobStatus,
    QuestionExtraction,
    StartImageAnalysisRequest,
)


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


def test_dispatcher_preserves_only_provider_error_code() -> None:
    jobs = InMemoryImageAnalysisJobRepository()
    job, _ = jobs.create(
        uuid4(),
        uuid4(),
        uuid4(),
        "image-analysis-provider-http-error",
        _request(),
        status=ImageAnalysisJobStatus.QUEUED,
        error_code=None,
    )

    class ProviderFailureRunner:
        def run(self, _job) -> UUID:
            raise NewApiProviderError("raw response must stay private", code="provider_http_403")

    result = ImageAnalysisDispatcher(jobs, ProviderFailureRunner()).run_once()

    assert result is not None
    assert result.status == "failed"
    receipt = jobs.get(job.household_id, job.capture_id, job.child_id, job.id)
    assert receipt.error_code == "provider_http_403"


def test_disabled_provider_keeps_default_worker_idle(monkeypatch) -> None:
    monkeypatch.setenv("STUDY_NEWAPI_ENABLED", "false")

    summary = run_worker_watch(build_worker, poll_interval=0, max_iterations=2)

    assert summary.status == "idle"
    assert summary.exit_code == 0


def _synthetic_png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (2, 2), color=(255, 255, 255)).save(output, format="PNG")
    return output.getvalue()


class _CaptureRepository:
    def __init__(self, data: bytes) -> None:
        self.capture = Capture(
            id=uuid4(),
            household_id=uuid4(),
            child_id=uuid4(),
            session_id=uuid4(),
            media_type="image/png",
            byte_size=len(data),
            content_sha256=sha256(data).hexdigest(),
            status=CaptureStatus.NEEDS_CORRECTION,
            version=1,
            created_at=datetime.now(UTC),
        )
        self.pending = PendingCaptureUpload(self.capture, "captures/synthetic/derivative")
        self.ocr_failures: list[tuple[UUID, UUID]] = []

    def get_capture_upload(self, household_id: UUID, capture_id: UUID, child_id: UUID):
        assert (household_id, capture_id, child_id) == (
            self.capture.household_id,
            self.capture.id,
            self.capture.child_id,
        )
        return self.pending

    def mark_capture_ocr_failed(self, household_id: UUID, capture_id: UUID) -> None:
        self.ocr_failures.append((household_id, capture_id))


class _Storage:
    def __init__(self, data: bytes, fail_delete: bool = False) -> None:
        self.data = data
        self.deleted: list[str] = []
        self.fail_delete = fail_delete

    def read_object(self, object_key: str, max_bytes: int) -> bytes:
        assert max_bytes == 8_000_000
        return self.data

    def delete_object(self, object_key: str) -> None:
        self.deleted.append(object_key)
        if self.fail_delete:
            raise RuntimeError("synthetic storage failure")


class _Provider:
    def analyze_sanitized_image(self, *_args, **_kwargs):
        return QuestionExtraction(
            subject="math",
            question_text="1 + 1 = ?",
            options=(),
            formulas=(),
            has_diagram=False,
            has_handwriting=False,
            question_region_count=1,
            confidence=0.9,
        )


def test_newapi_runner_deletes_sanitized_derivative_after_success() -> None:
    data = _synthetic_png()
    captures = _CaptureRepository(data)
    storage = _Storage(data)
    jobs = InMemoryImageAnalysisJobRepository()
    _job, _ = jobs.create(
        captures.capture.household_id,
        captures.capture.id,
        captures.capture.child_id,
        "worker-cleanup-success",
        _request().model_copy(
            update={
                "sanitization": _request().sanitization.model_copy(
                    update={"sanitized_derivative_sha256": sha256(data).hexdigest()}
                )
            }
        ),
        status=ImageAnalysisJobStatus.QUEUED,
        error_code=None,
    )
    claimed = jobs.claim_next()
    assert claimed is not None
    runner = NewApiImageAnalysisRunner(
        captures, storage, _Provider(), InMemoryQuestionExtractionRepository()
    )

    runner.run(claimed)

    assert storage.deleted == [captures.pending.object_key]
    assert captures.ocr_failures == []


def test_newapi_runner_marks_bounded_failure_when_derivative_delete_fails() -> None:
    data = _synthetic_png()
    captures = _CaptureRepository(data)
    storage = _Storage(data, fail_delete=True)
    jobs = InMemoryImageAnalysisJobRepository()
    request = _request().model_copy(
        update={
            "sanitization": _request().sanitization.model_copy(
                update={"sanitized_derivative_sha256": sha256(data).hexdigest()}
            )
        }
    )
    _job, _ = jobs.create(
        captures.capture.household_id,
        captures.capture.id,
        captures.capture.child_id,
        "worker-cleanup-failure",
        request,
        status=ImageAnalysisJobStatus.QUEUED,
        error_code=None,
    )
    claimed = jobs.claim_next()
    assert claimed is not None
    runner = NewApiImageAnalysisRunner(
        captures, storage, _Provider(), InMemoryQuestionExtractionRepository()
    )

    with pytest.raises(RuntimeError):
        runner.run(claimed)

    assert captures.ocr_failures == [(captures.capture.household_id, captures.capture.id)]
