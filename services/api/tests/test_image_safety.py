import base64
from io import BytesIO

import pytest
from PIL import Image

from study_api.image_safety import (
    ImageSafetyError,
    normalize_image_for_ocr,
    validate_image_headers,
)

JPEG_1X1 = bytes.fromhex("ffd8ffe000040000ffc0000b080001000101011100ffda0008010100003f0000ffd9")
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
JPEG_1X1_EXIF = bytes.fromhex("ffd8ffe1000a4578696600000000") + JPEG_1X1[2:]


def _valid_jpeg() -> bytes:
    output = BytesIO()
    Image.new("RGB", (2, 2), (255, 0, 0)).save(output, format="JPEG")
    return output.getvalue()


def test_validate_image_headers_accepts_synthetic_jpeg_and_png() -> None:
    jpeg = validate_image_headers(JPEG_1X1, "image/jpeg")
    png = validate_image_headers(PNG_1X1, "image/png")

    assert (jpeg.format, jpeg.width, jpeg.height, jpeg.has_exif) == ("jpeg", 1, 1, False)
    assert (png.format, png.width, png.height, png.has_exif) == ("png", 1, 1, False)


@pytest.mark.parametrize(
    ("data", "content_type"),
    [(JPEG_1X1, "image/png"), (PNG_1X1, "image/jpeg"), (b"not-an-image", "image/jpeg")],
)
def test_validate_image_headers_rejects_mismatched_or_invalid_containers(
    data: bytes, content_type: str
) -> None:
    with pytest.raises(ImageSafetyError):
        validate_image_headers(data, content_type)


def test_validate_image_headers_rejects_exif_until_a_sanitizer_exists() -> None:
    with pytest.raises(ImageSafetyError, match="sanitized"):
        validate_image_headers(JPEG_1X1_EXIF, "image/jpeg")

    metadata = validate_image_headers(JPEG_1X1_EXIF, "image/jpeg", reject_exif=False)
    assert metadata.has_exif is True


def test_validate_image_headers_rejects_corrupt_png_header_checksum() -> None:
    corrupt = PNG_1X1[:29] + bytes([PNG_1X1[29] ^ 0x01]) + PNG_1X1[30:]

    with pytest.raises(ImageSafetyError, match="checksum"):
        validate_image_headers(corrupt, "image/png")


def test_normalize_image_decodes_pixels_and_removes_exif() -> None:
    output = BytesIO()
    image = Image.new("RGB", (2, 2), (255, 0, 0))
    exif = Image.Exif()
    exif[0x010E] = "synthetic metadata"
    image.save(output, format="JPEG", exif=exif)

    normalized = normalize_image_for_ocr(output.getvalue(), "image/jpeg")

    assert normalized.metadata == validate_image_headers(normalized.data, "image/jpeg")
    assert normalized.metadata.has_exif is False
    assert normalized.data != output.getvalue()
    with Image.open(BytesIO(normalized.data)) as decoded:
        assert decoded.size == (2, 2)
        assert decoded.getexif() == {}


def test_normalize_image_rejects_truncated_pixels_after_header_checks() -> None:
    valid = _valid_jpeg()
    scan_start = valid.index(b"\xff\xda")
    truncated = valid[: scan_start + 10] + b"abc\xff\xd9"

    with pytest.raises(ImageSafetyError, match="pixels"):
        normalize_image_for_ocr(truncated, "image/jpeg")
