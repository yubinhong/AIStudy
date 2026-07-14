import base64
from hashlib import sha256

import pytest

from study_api.capture_media import read_safe_capture
from study_api.image_safety import ImageSafetyError

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class FakeCaptureStorage:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.requested_limit: int | None = None

    def read_object(self, object_key: str, max_bytes: int) -> bytes:
        assert object_key.startswith("captures/")
        self.requested_limit = max_bytes
        return self.data


def test_read_safe_capture_verifies_hash_size_and_normalizes_pixels() -> None:
    storage = FakeCaptureStorage(PNG_1X1)

    result = read_safe_capture(
        storage,
        "captures/synthetic/source",
        "image/png",
        len(PNG_1X1),
        sha256(PNG_1X1).hexdigest(),
    )

    assert result.metadata.width == 1
    assert result.metadata.height == 1
    assert result.data != PNG_1X1
    assert result.data[:8] == b"\x89PNG\r\n\x1a\n"
    assert storage.requested_limit == 8_000_000


def test_read_safe_capture_rejects_changed_bytes_before_ocr() -> None:
    storage = FakeCaptureStorage(PNG_1X1 + b"changed")

    with pytest.raises(ImageSafetyError, match="size"):
        read_safe_capture(
            storage,
            "captures/synthetic/source",
            "image/png",
            len(PNG_1X1),
            sha256(PNG_1X1).hexdigest(),
        )


def test_read_safe_capture_rejects_a_digest_mismatch() -> None:
    storage = FakeCaptureStorage(PNG_1X1)

    with pytest.raises(ImageSafetyError, match="digest"):
        read_safe_capture(
            storage,
            "captures/synthetic/source",
            "image/png",
            len(PNG_1X1),
            sha256(b"different").hexdigest(),
        )
