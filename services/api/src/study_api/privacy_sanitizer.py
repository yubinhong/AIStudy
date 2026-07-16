"""Local, Provider-independent image sanitization for ADR-0015.

Detection is intentionally injected as structured signals.  A future OCR,
rule, or lightweight vision detector may produce those signals, but this
module never persists or logs the text that led to a region.  The returned
derivative is an in-memory handoff; object storage, confirmation, and cloud
Provider gates are separate future boundaries.
"""

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from typing import Literal

from PIL import Image, ImageDraw
from pydantic import BaseModel, ConfigDict, Field

from study_api.image_safety import ImageSafetyError, normalize_image_for_ocr
from study_api.privacy_models import (
    PrivacySanitization,
    SensitiveRegionKind,
)

SANITIZER_VERSION = "privacy-sanitizer.synthetic-v1"
MIN_REGION_CONFIDENCE = 0.8
MAX_FACE_AREA_RATIO = 0.25
REGION_MARGIN_PX = 2
BLOCK_COLOR = (0, 0, 0)


class PrivacySanitizationError(ValueError):
    """Raised when a source or detector signal cannot safely be sanitized."""


class SensitiveRegion(BaseModel):
    """A pixel rectangle; it contains no recognized text."""

    model_config = ConfigDict(frozen=True)

    kind: SensitiveRegionKind
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    confidence: float = Field(ge=0.0, le=1.0)
    source: Literal["ocr", "rule", "vision", "manual"]


class SanitizerSignals(BaseModel):
    """Detector output accepted by the sanitizer without accepting raw text."""

    model_config = ConfigDict(frozen=True)

    regions: tuple[SensitiveRegion, ...] = Field(default=(), max_length=256)
    face_detected: bool = False
    face_area_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    face_ambiguous: bool = False
    qr_detected: bool = False
    barcode_detected: bool = False
    low_confidence: bool = False
    crop_incomplete: bool = False


@dataclass(frozen=True)
class SanitizedDerivative:
    """In-memory derivative plus metadata; callers must not log ``data``."""

    data: bytes
    metadata: PrivacySanitization


def _unique(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _validate_region(region: SensitiveRegion, width: int, height: int) -> None:
    if region.x + region.width > width or region.y + region.height > height:
        raise PrivacySanitizationError("sensitive region is outside image bounds")


class PrivacySanitizer:
    """Generate an irreversible, metadata-free derivative in memory."""

    def sanitize(
        self,
        data: bytes,
        content_type: Literal["image/jpeg", "image/png"],
        signals: SanitizerSignals,
    ) -> SanitizedDerivative:
        try:
            normalized = normalize_image_for_ocr(data, content_type)
        except ImageSafetyError as error:
            raise PrivacySanitizationError("image cannot be sanitized") from error

        try:
            with Image.open(BytesIO(normalized.data)) as source:
                source.load()
                image = source.convert("RGB")
        except Exception as error:  # noqa: BLE001 -- decoder details must not escape.
            raise PrivacySanitizationError("image pixels cannot be sanitized") from error

        for region in signals.regions:
            _validate_region(region, image.width, image.height)

        blocked: list[str] = []
        if signals.low_confidence:
            blocked.append("low_detection_confidence")
        if signals.crop_incomplete:
            blocked.append("incomplete_single_question_crop")
        if signals.face_detected and signals.face_area_ratio > MAX_FACE_AREA_RATIO:
            blocked.append("large_face")
        if signals.face_detected and signals.face_ambiguous:
            blocked.append("ambiguous_face")

        region_kinds = {region.kind for region in signals.regions}
        if signals.face_detected and SensitiveRegionKind.FACE not in region_kinds:
            blocked.append("face_region_missing")
        if signals.qr_detected and SensitiveRegionKind.QR_CODE not in region_kinds:
            blocked.append("qr_region_missing")
        if signals.barcode_detected and SensitiveRegionKind.BARCODE not in region_kinds:
            blocked.append("barcode_region_missing")

        for region in signals.regions:
            if region.confidence < MIN_REGION_CONFIDENCE:
                blocked.append("low_region_confidence")

        if signals.regions:
            draw = ImageDraw.Draw(image)
            for region in signals.regions:
                left = max(0, region.x - REGION_MARGIN_PX)
                top = max(0, region.y - REGION_MARGIN_PX)
                right = min(image.width - 1, region.x + region.width - 1 + REGION_MARGIN_PX)
                bottom = min(image.height - 1, region.y + region.height - 1 + REGION_MARGIN_PX)
                draw.rectangle(
                    (left, top, right, bottom),
                    fill=BLOCK_COLOR,
                )

        output = BytesIO()
        if content_type == "image/jpeg":
            image.save(output, format="JPEG", quality=95, optimize=True)
        else:
            image.save(output, format="PNG", optimize=True)
        derivative = normalize_image_for_ocr(output.getvalue(), content_type)
        derivative_hash = sha256(derivative.data).hexdigest()
        metadata = PrivacySanitization(
            sanitizer_version=SANITIZER_VERSION,
            safe_to_upload=not blocked,
            sensitive_types=tuple(sorted(region_kinds, key=lambda kind: kind.value)),
            region_count=len(signals.regions),
            face_detected=signals.face_detected,
            qr_detected=signals.qr_detected,
            barcode_detected=signals.barcode_detected,
            blocked_reasons=_unique(blocked),
            sanitized_derivative_sha256=derivative_hash,
        )
        return SanitizedDerivative(data=derivative.data, metadata=metadata)
