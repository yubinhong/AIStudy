from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from study_api.domain.models import OcrJobStatus, OcrMode, OcrResult, OcrResultStatus
from study_api.ocr_jobs import (
    InMemoryOcrJobQueue,
    LocalOcrDispatcher,
    OcrJobIdempotencyConflictError,
)

HOUSEHOLD_ID = UUID("00000000-0000-0000-0000-000000000001")
CAPTURE_ID = UUID("00000000-0000-0000-0000-000000000201")
CHILD_ID = UUID("00000000-0000-0000-0000-000000000101")


def _result() -> OcrResult:
    return OcrResult(
        id=uuid4(),
        capture_id=CAPTURE_ID,
        household_id=HOUSEHOLD_ID,
        child_id=CHILD_ID,
        provider="local_paddleocr",
        model="PP-OCRv6_medium",
        model_version="synthetic",
        schema_version="ocr-result.v1",
        confidence=0.9,
        status=OcrResultStatus.CANDIDATE,
        requires_manual_confirmation=True,
        created_at=datetime.now(UTC),
    )


class FakeRunner:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[UUID, UUID, UUID, str, OcrMode]] = []

    def run(
        self,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        idempotency_key: str,
        mode: OcrMode = OcrMode.TEXT,
    ) -> tuple[OcrResult, bool]:
        self.calls.append((household_id, capture_id, child_id, idempotency_key, mode))
        if self.fail:
            raise RuntimeError("synthetic provider secret")
        return _result(), False


def test_queue_is_idempotent_and_claims_only_queued_jobs() -> None:
    queue = InMemoryOcrJobQueue()
    first, replayed = queue.enqueue(HOUSEHOLD_ID, CAPTURE_ID, CHILD_ID, "ocr-queue-001")
    same, replayed_again = queue.enqueue(HOUSEHOLD_ID, CAPTURE_ID, CHILD_ID, "ocr-queue-001")

    assert replayed is False
    assert replayed_again is True
    assert same == first
    assert queue.claim_next() == queue.get(first.id)
    assert queue.get(first.id).status is OcrJobStatus.RUNNING
    assert queue.claim_next() is None

    queue.complete(first.id, uuid4())
    assert queue.get(first.id).status is OcrJobStatus.SUCCEEDED


def test_queue_defaults_to_text_and_rejects_mode_idempotency_reuse() -> None:
    queue = InMemoryOcrJobQueue()
    first, replayed = queue.enqueue(
        HOUSEHOLD_ID,
        CAPTURE_ID,
        CHILD_ID,
        "ocr-mode-001",
        mode=OcrMode.FORMULA,
    )

    assert replayed is False
    assert first.mode is OcrMode.FORMULA
    assert queue.get(first.id).receipt().mode is OcrMode.FORMULA
    with pytest.raises(OcrJobIdempotencyConflictError):
        queue.enqueue(HOUSEHOLD_ID, CAPTURE_ID, CHILD_ID, "ocr-mode-001")


def test_dispatcher_completes_successful_job_without_provider_payload() -> None:
    queue = InMemoryOcrJobQueue()
    job, _ = queue.enqueue(HOUSEHOLD_ID, CAPTURE_ID, CHILD_ID, "ocr-dispatch-001")
    runner = FakeRunner()

    outcome = LocalOcrDispatcher(queue, runner).run_once()

    assert outcome is not None
    assert outcome.job_id == job.id
    assert outcome.status is OcrJobStatus.SUCCEEDED
    assert outcome.result_id is not None
    assert queue.get(job.id).result_id == outcome.result_id
    assert runner.calls[0][:3] == (HOUSEHOLD_ID, CAPTURE_ID, CHILD_ID)
    assert runner.calls[0][3].startswith("ocr-worker:")
    assert runner.calls[0][4] is OcrMode.TEXT


def test_dispatcher_marks_failure_with_stable_code_and_allows_new_retry_job() -> None:
    queue = InMemoryOcrJobQueue()
    job, _ = queue.enqueue(HOUSEHOLD_ID, CAPTURE_ID, CHILD_ID, "ocr-dispatch-002")

    outcome = LocalOcrDispatcher(queue, FakeRunner(fail=True)).run_once()

    assert outcome is not None
    assert outcome.status is OcrJobStatus.FAILED
    failed = queue.get(job.id)
    assert failed.error_code == "ocr_job_failed"
    assert "synthetic provider secret" not in str(failed)

    retry, replayed = queue.enqueue(HOUSEHOLD_ID, CAPTURE_ID, CHILD_ID, "ocr-dispatch-003")
    assert replayed is False
    assert retry.id != job.id
    assert retry.status is OcrJobStatus.QUEUED
