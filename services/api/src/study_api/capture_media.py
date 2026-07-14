"""Read and validate Capture bytes at the boundary before OCR scheduling."""

from dataclasses import dataclass
from hashlib import sha256
from hmac import compare_digest

from study_api.image_safety import ImageMetadata, ImageSafetyError, normalize_image_for_ocr
from study_api.object_storage import CaptureObjectStorage


@dataclass(frozen=True)
class SafeCaptureInput:
    """Bounded in-memory bytes; callers must not persist or log ``data``."""

    data: bytes
    metadata: ImageMetadata


def read_safe_capture(
    object_storage: CaptureObjectStorage,
    object_key: str,
    content_type: str,
    byte_size: int,
    content_sha256: str,
) -> SafeCaptureInput:
    """Read one private object and verify its declared integrity before OCR."""

    if not 1 <= byte_size <= 8_000_000:
        raise ImageSafetyError("capture byte size is not allowed")
    data = object_storage.read_object(object_key, max_bytes=8_000_000)
    if len(data) != byte_size:
        raise ImageSafetyError("capture object size does not match declaration")
    digest = sha256(data).hexdigest()
    if not compare_digest(digest, content_sha256):
        raise ImageSafetyError("capture object digest does not match declaration")
    normalized = normalize_image_for_ocr(data, content_type)
    return SafeCaptureInput(data=normalized.data, metadata=normalized.metadata)
