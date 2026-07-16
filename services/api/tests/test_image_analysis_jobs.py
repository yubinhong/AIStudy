from uuid import uuid4

from study_api.image_analysis_jobs import InMemoryImageAnalysisJobRepository
from study_api.privacy_models import ImageAnalysisJobStatus, StartImageAnalysisRequest


def _request() -> StartImageAnalysisRequest:
    return StartImageAnalysisRequest(
        expected_capture_version=2,
        sanitization={
            "sanitizer_version": "synthetic-v1",
            "safe_to_upload": True,
            "sensitive_types": [],
            "region_count": 0,
            "face_detected": False,
            "qr_detected": False,
            "barcode_detected": False,
            "blocked_reasons": [],
            "sanitized_derivative_sha256": "a" * 64,
        },
    )


def test_in_memory_image_analysis_job_claim_and_completion() -> None:
    repository = InMemoryImageAnalysisJobRepository()
    household_id, capture_id, child_id = uuid4(), uuid4(), uuid4()
    job, replayed = repository.create(
        household_id,
        capture_id,
        child_id,
        "image-analysis-idempotency",
        _request(),
        status=ImageAnalysisJobStatus.QUEUED,
        error_code=None,
    )

    assert replayed is False
    claimed = repository.claim_next()
    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.status is ImageAnalysisJobStatus.RUNNING
    extraction_id = uuid4()
    repository.complete(job.id, extraction_id)

    receipt = repository.get(household_id, capture_id, child_id, job.id)
    assert receipt.status is ImageAnalysisJobStatus.SUCCEEDED
    assert receipt.extraction_id == extraction_id
    assert repository.claim_next() is None
