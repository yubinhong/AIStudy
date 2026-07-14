from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from PIL import Image

from study_api.domain.capture_repository import CaptureStateError, PendingCaptureUpload
from study_api.domain.models import Capture, CaptureStatus, OcrResult, OcrResultStatus
from study_api.domain.ocr_result_repository import OcrResultDraft
from study_api.ocr_provider import OcrExecutionError, OcrParseResult, parse_paddle_text_result
from study_api.ocr_service import LocalOcrJob, OcrJobError

HOUSEHOLD_ID = UUID("00000000-0000-0000-0000-000000000001")
CHILD_ID = UUID("00000000-0000-0000-0000-000000000101")


def _png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (2, 2), color=(255, 255, 255)).save(output, format="PNG")
    return output.getvalue()


class FakeCaptureRepository:
    def __init__(self, capture: Capture, object_key: str = "captures/synthetic/source") -> None:
        self.pending = PendingCaptureUpload(capture, object_key)
        self.ocr_failures: list[tuple[UUID, UUID]] = []

    def get_capture_upload(
        self, household_id: UUID, capture_id: UUID, child_id: UUID
    ) -> PendingCaptureUpload:
        assert household_id == HOUSEHOLD_ID
        assert capture_id == self.pending.capture.id
        assert child_id == CHILD_ID
        return self.pending

    def mark_capture_ocr_failed(self, household_id: UUID, capture_id: UUID) -> None:
        self.ocr_failures.append((household_id, capture_id))


class FakeStorage:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.read_keys: list[str] = []

    def read_object(self, object_key: str, max_bytes: int) -> bytes:
        self.read_keys.append(object_key)
        assert max_bytes == 8_000_000
        return self.data


class FakeAdapter:
    def __init__(self, result: OcrParseResult | Exception) -> None:
        self.result = result
        self.received: list[object] = []

    def run_text_ocr(self, capture: object, *, confidence_threshold: float = 0.8) -> OcrParseResult:
        self.received.append(capture)
        if isinstance(self.result, Exception):
            raise self.result
        assert confidence_threshold == 0.8
        return self.result


class FakeResultRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, UUID, UUID, OcrResultDraft, str]] = []

    def create_result(
        self,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        draft: OcrResultDraft,
        idempotency_key: str,
    ) -> tuple[OcrResult, bool]:
        self.calls.append((household_id, capture_id, child_id, draft, idempotency_key))
        result = OcrResult(
            id=uuid4(),
            capture_id=capture_id,
            household_id=household_id,
            child_id=child_id,
            provider=draft.provider,
            model=draft.model,
            model_version=draft.model_version,
            schema_version=draft.schema_version,
            confidence=draft.confidence,
            status=draft.status,
            requires_manual_confirmation=True,
            created_at=datetime.now(UTC),
        )
        return result, False


def _capture(data: bytes, status: CaptureStatus = CaptureStatus.NEEDS_CORRECTION) -> Capture:
    return Capture(
        id=uuid4(),
        household_id=HOUSEHOLD_ID,
        child_id=CHILD_ID,
        session_id=uuid4(),
        media_type="image/png",
        byte_size=len(data),
        content_sha256=sha256(data).hexdigest(),
        status=status,
        version=2,
        created_at=datetime.now(UTC),
    )


def test_local_ocr_job_reads_safely_normalizes_and_persists_manual_candidate() -> None:
    data = _png()
    captures = FakeCaptureRepository(_capture(data))
    storage = FakeStorage(data)
    adapter = FakeAdapter(parse_paddle_text_result({"rec_texts": ["12 + 3"], "rec_scores": [0.93]}))
    results = FakeResultRepository()

    result, replayed = LocalOcrJob(captures, storage, adapter, results).run(
        HOUSEHOLD_ID, captures.pending.capture.id, CHILD_ID, "ocr-job-001"
    )

    assert replayed is False
    assert result.requires_manual_confirmation is True
    assert result.status is OcrResultStatus.CANDIDATE
    assert storage.read_keys == ["captures/synthetic/source"]
    assert len(adapter.received) == 1
    assert len(results.calls) == 1
    assert results.calls[0][3].candidates[0].text == "12 + 3"
    assert captures.ocr_failures == []


def test_local_ocr_job_rejects_pending_upload_before_reading_storage() -> None:
    data = _png()
    captures = FakeCaptureRepository(_capture(data, CaptureStatus.UPLOAD_PENDING))
    storage = FakeStorage(data)
    adapter = FakeAdapter(parse_paddle_text_result({"rec_texts": [], "rec_scores": []}))
    results = FakeResultRepository()

    with pytest.raises(CaptureStateError):
        LocalOcrJob(captures, storage, adapter, results).run(
            HOUSEHOLD_ID, captures.pending.capture.id, CHILD_ID, "ocr-job-pending"
        )

    assert storage.read_keys == []
    assert adapter.received == []
    assert results.calls == []
    assert captures.ocr_failures == []


def test_local_ocr_job_does_not_persist_invalid_image_or_provider_failure() -> None:
    valid_data = _png()
    captures = FakeCaptureRepository(_capture(valid_data))
    results = FakeResultRepository()

    invalid_storage = FakeStorage(b"not-an-image")
    invalid_adapter = FakeAdapter(parse_paddle_text_result({"rec_texts": [], "rec_scores": []}))
    with pytest.raises(OcrJobError):
        LocalOcrJob(captures, invalid_storage, invalid_adapter, results).run(
            HOUSEHOLD_ID, captures.pending.capture.id, CHILD_ID, "ocr-job-invalid"
        )

    failing_storage = FakeStorage(valid_data)
    failing_adapter = FakeAdapter(OcrExecutionError("provider detail must stay private"))
    with pytest.raises(OcrJobError):
        LocalOcrJob(captures, failing_storage, failing_adapter, results).run(
            HOUSEHOLD_ID, captures.pending.capture.id, CHILD_ID, "ocr-job-failure"
        )

    assert results.calls == []
    assert captures.ocr_failures == [
        (HOUSEHOLD_ID, captures.pending.capture.id),
        (HOUSEHOLD_ID, captures.pending.capture.id),
    ]
