"""Transient OCR/rule signals for the local PrivacySanitizer.

This module consumes OCR text only inside the local trust boundary.  It emits
coordinates and stable sensitive-type enums, never the matched text.  It is a
detector adapter, not a question parser and not a cloud Provider client.
"""

import re
from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from study_api.privacy_models import SensitiveRegionKind
from study_api.privacy_sanitizer import MIN_REGION_CONFIDENCE, SanitizerSignals, SensitiveRegion

_LABELS: tuple[tuple[str, SensitiveRegionKind], ...] = (
    ("姓名", SensitiveRegionKind.NAME),
    ("学校", SensitiveRegionKind.SCHOOL),
    ("班级", SensitiveRegionKind.CLASS),
    ("年级", SensitiveRegionKind.GRADE),
    ("学号", SensitiveRegionKind.STUDENT_ID),
    ("考号", SensitiveRegionKind.EXAM_ID),
    ("座号", SensitiveRegionKind.SEAT_NUMBER),
    ("电话", SensitiveRegionKind.PHONE),
    ("手机", SensitiveRegionKind.PHONE),
    ("地址", SensitiveRegionKind.ADDRESS),
    ("签名", SensitiveRegionKind.SIGNATURE),
)
_RULES: tuple[tuple[re.Pattern[str], SensitiveRegionKind], ...] = (
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), SensitiveRegionKind.PHONE),
    (re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"), SensitiveRegionKind.PHONE),
    (re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"), SensitiveRegionKind.STUDENT_ID),
)


class OcrTextBox(BaseModel):
    """Transient OCR output required for localization, without persistence."""

    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1, max_length=1_000)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("text")
    @classmethod
    def text_has_no_controls(cls, value: str) -> str:
        if any(ord(character) < 0x20 for character in value):
            raise ValueError("OCR text cannot contain control characters")
        return value


def _nearby(left: OcrTextBox, right: OcrTextBox) -> bool:
    left_center = left.y + left.height / 2
    right_center = right.y + right.height / 2
    vertical_gap = abs(left_center - right_center)
    horizontal_gap = right.x - (left.x + left.width)
    return 0 <= horizontal_gap <= max(left.width * 3, 80) and vertical_gap <= max(
        left.height, right.height
    )


class LocalPrivacyDetector:
    """Map transient OCR boxes to conservative sanitization signals."""

    def detect(self, boxes: Iterable[OcrTextBox]) -> SanitizerSignals:
        items = tuple(boxes)
        regions: list[SensitiveRegion] = []
        low_confidence = any(box.confidence < MIN_REGION_CONFIDENCE for box in items)

        for index, box in enumerate(items):
            for label, kind in _LABELS:
                if label not in box.text:
                    continue
                regions.append(self._region(box, kind, "ocr"))
                for candidate in items[index + 1 :]:
                    if _nearby(box, candidate):
                        regions.append(self._region(candidate, kind, "ocr"))
                        break

            for pattern, kind in _RULES:
                if pattern.search(box.text):
                    regions.append(self._region(box, kind, "rule"))

        unique: dict[tuple[SensitiveRegionKind, int, int, int, int], SensitiveRegion] = {}
        for region in regions:
            key = (region.kind, region.x, region.y, region.width, region.height)
            unique[key] = region
        return SanitizerSignals(regions=tuple(unique.values()), low_confidence=low_confidence)

    @staticmethod
    def _region(
        box: OcrTextBox,
        kind: SensitiveRegionKind,
        source: Literal["ocr", "rule"],
    ) -> SensitiveRegion:
        return SensitiveRegion(
            kind=kind,
            x=box.x,
            y=box.y,
            width=box.width,
            height=box.height,
            confidence=box.confidence,
            source=source,
        )
