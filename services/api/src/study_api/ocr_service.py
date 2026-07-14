"""Application boundary for one local OCR job.

The service keeps object reads, image sanitization, Provider execution, and
candidate persistence in one explicit flow. It does not expose object keys or
raw Provider responses to callers.
"""

from collections.abc import Callable
from typing import Protocol
from uuid import UUID

from study_api.capture_media import SafeCaptureInput, read_safe_capture
from study_api.domain.capture_repository import CaptureRepository, CaptureStateError
from study_api.domain.models import CaptureStatus, OcrResult
from study_api.domain.ocr_result_repository import OcrResultDraft, OcrResultRepository
from study_api.image_safety import ImageSafetyError
from study_api.object_storage import CaptureObjectStorage, ObjectStorageError
from study_api.ocr_provider import OcrExecutionError, OcrParseResult, OcrResultError


class OcrJobError(RuntimeError):
    """Raised when a local OCR job fails without exposing Provider details."""


class TextOcrAdapter(Protocol):
    def run_text_ocr(
        self,
        capture: SafeCaptureInput,
        *,
        confidence_threshold: float = 0.8,
    ) -> OcrParseResult: ...


class LocalOcrJob:
    """Run one confirmed Capture through the local OCR trust boundary."""

    def __init__(
        self,
        capture_repository: CaptureRepository,
        object_storage: CaptureObjectStorage,
        ocr_adapter: TextOcrAdapter,
        result_repository: OcrResultRepository,
        *,
        confidence_threshold: float = 0.8,
        draft_factory: Callable[
            [OcrParseResult], OcrResultDraft
        ] = OcrResultDraft.from_parse_result,
    ) -> None:
        self._captures = capture_repository
        self._storage = object_storage
        self._adapter = ocr_adapter
        self._results = result_repository
        self._confidence_threshold = confidence_threshold
        self._draft_factory = draft_factory

    def run(
        self,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        idempotency_key: str,
    ) -> tuple[OcrResult, bool]:
        pending = self._captures.get_capture_upload(household_id, capture_id, child_id)
        if pending.capture.status is CaptureStatus.UPLOAD_PENDING:
            raise CaptureStateError
        try:
            safe_capture = read_safe_capture(
                self._storage,
                pending.object_key,
                pending.capture.media_type,
                pending.capture.byte_size,
                pending.capture.content_sha256,
            )
            parsed = self._adapter.run_text_ocr(
                safe_capture,
                confidence_threshold=self._confidence_threshold,
            )
            draft = self._draft_factory(parsed)
        except (ObjectStorageError, ImageSafetyError, OcrExecutionError, OcrResultError) as error:
            self._mark_failure(household_id, capture_id)
            raise OcrJobError("local OCR job failed") from error
        except Exception as error:  # noqa: BLE001 -- Provider details must not escape.
            self._mark_failure(household_id, capture_id)
            raise OcrJobError("local OCR job failed") from error
        return self._results.create_result(
            household_id,
            capture_id,
            child_id,
            draft,
            idempotency_key,
        )

    def _mark_failure(self, household_id: UUID, capture_id: UUID) -> None:
        try:
            self._captures.mark_capture_ocr_failed(household_id, capture_id)
        except Exception as error:  # noqa: BLE001 -- do not expose persistence details.
            raise OcrJobError("local OCR job failed") from error
