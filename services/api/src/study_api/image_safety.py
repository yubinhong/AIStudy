"""Bounded image-container checks before an object can enter OCR."""

import binascii
import struct
from dataclasses import dataclass
from io import BytesIO
from typing import Literal

from PIL import Image, ImageOps

MAX_CAPTURE_BYTES = 8_000_000
MAX_IMAGE_DIMENSION = 10_000
MAX_IMAGE_PIXELS = 25_000_000


class ImageSafetyError(ValueError):
    """Raised when a bounded Capture image cannot safely enter OCR."""


@dataclass(frozen=True)
class ImageMetadata:
    format: Literal["jpeg", "png"]
    width: int
    height: int
    has_exif: bool


@dataclass(frozen=True)
class SanitizedImage:
    """Decoded pixels re-encoded without source metadata for the OCR boundary."""

    data: bytes
    metadata: ImageMetadata


def _check_dimensions(width: int, height: int) -> None:
    if not 1 <= width <= MAX_IMAGE_DIMENSION or not 1 <= height <= MAX_IMAGE_DIMENSION:
        raise ImageSafetyError("image dimensions are not allowed")
    if width * height > MAX_IMAGE_PIXELS:
        raise ImageSafetyError("image pixel count is not allowed")


def _jpeg_dimensions(data: bytes) -> tuple[int, int, bool]:
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        raise ImageSafetyError("image bytes do not match JPEG")

    sof_markers = {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
    position = 2
    width: int | None = None
    height: int | None = None
    has_exif = False

    while position < len(data):
        if data[position] != 0xFF:
            raise ImageSafetyError("JPEG marker stream is invalid")
        while position < len(data) and data[position] == 0xFF:
            position += 1
        if position >= len(data):
            break
        marker = data[position]
        position += 1
        if marker == 0x00:
            raise ImageSafetyError("JPEG marker stream is invalid")
        if marker == 0xDA:  # Start of scan; dimensions must have appeared before pixels.
            if position + 2 > len(data):
                raise ImageSafetyError("JPEG scan header is truncated")
            segment_length = struct.unpack_from(">H", data, position)[0]
            if segment_length < 2 or position + segment_length > len(data):
                raise ImageSafetyError("JPEG scan header is invalid")
            position += segment_length
            break
        if marker in {0x01, 0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if position + 2 > len(data):
            raise ImageSafetyError("JPEG segment is truncated")
        segment_length = struct.unpack_from(">H", data, position)[0]
        if segment_length < 2 or position + segment_length > len(data):
            raise ImageSafetyError("JPEG segment is invalid")
        segment = data[position + 2 : position + segment_length]
        if marker == 0xE1 and segment.startswith(b"Exif\x00\x00"):
            has_exif = True
        if marker in sof_markers:
            if len(segment) < 5:
                raise ImageSafetyError("JPEG frame header is invalid")
            height, width = struct.unpack_from(">HH", segment, 1)
        position += segment_length

    if width is None or height is None or data.rfind(b"\xff\xd9") < 0:
        raise ImageSafetyError("JPEG frame is incomplete")
    _check_dimensions(width, height)
    return width, height, has_exif


def _png_dimensions(data: bytes) -> tuple[int, int]:
    signature = b"\x89PNG\r\n\x1a\n"
    if len(data) < 33 or data[:8] != signature:
        raise ImageSafetyError("image bytes do not match PNG")
    if struct.unpack_from(">I", data, 8)[0] != 13 or data[12:16] != b"IHDR":
        raise ImageSafetyError("PNG header is invalid")
    ihdr_end = 29
    expected_crc = struct.unpack_from(">I", data, ihdr_end)[0]
    actual_crc = binascii.crc32(data[12:ihdr_end]) & 0xFFFFFFFF
    if expected_crc != actual_crc:
        raise ImageSafetyError("PNG header checksum is invalid")
    if b"IEND" not in data:
        raise ImageSafetyError("PNG frame is incomplete")
    width, height = struct.unpack_from(">II", data, 16)
    _check_dimensions(width, height)
    return width, height


def validate_image_headers(
    data: bytes,
    content_type: str,
    *,
    reject_exif: bool = True,
) -> ImageMetadata:
    """Validate type, bounded size, container header and dimensions.

    This deliberately does not claim full pixel decoding or EXIF stripping. JPEG EXIF is
    rejected by default until a dedicated sanitizer is added before OCR.
    """

    if not 1 <= len(data) <= MAX_CAPTURE_BYTES:
        raise ImageSafetyError("image byte size is not allowed")
    if content_type == "image/jpeg":
        width, height, has_exif = _jpeg_dimensions(data)
        if has_exif and reject_exif:
            raise ImageSafetyError("image metadata must be sanitized before OCR")
        return ImageMetadata("jpeg", width, height, has_exif)
    if content_type == "image/png":
        width, height = _png_dimensions(data)
        return ImageMetadata("png", width, height, False)
    raise ImageSafetyError("image media type is not allowed")


def normalize_image_for_ocr(data: bytes, content_type: str) -> SanitizedImage:
    """Decode bounded pixels and re-encode without EXIF or ancillary metadata."""

    source_metadata = validate_image_headers(data, content_type, reject_exif=False)
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    try:
        with Image.open(BytesIO(data)) as source:
            expected_format = "JPEG" if content_type == "image/jpeg" else "PNG"
            if source.format != expected_format or source.size != (
                source_metadata.width,
                source_metadata.height,
            ):
                raise ImageSafetyError("decoded image metadata does not match declaration")
            source.load()
            pixels = ImageOps.exif_transpose(source)
            output = BytesIO()
            if content_type == "image/jpeg":
                if pixels.mode not in {"L", "RGB"}:
                    pixels = pixels.convert("RGB")
                pixels.save(output, format="JPEG", quality=95, optimize=True)
            else:
                pixels.save(output, format="PNG", optimize=True)
    except ImageSafetyError:
        raise
    except Exception as error:  # noqa: BLE001 -- decoder details must not escape.
        raise ImageSafetyError("image pixels cannot be decoded") from error

    normalized = output.getvalue()
    if not 1 <= len(normalized) <= MAX_CAPTURE_BYTES:
        raise ImageSafetyError("normalized image size is not allowed")
    metadata = validate_image_headers(normalized, content_type)
    if metadata.has_exif:
        raise ImageSafetyError("image metadata could not be sanitized")
    return SanitizedImage(data=normalized, metadata=metadata)
