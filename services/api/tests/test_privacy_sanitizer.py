from io import BytesIO

import pytest
from PIL import Image

from study_api.privacy_models import (
    PrivacySanitization,
    QuestionExtraction,
    SensitiveRegionKind,
)
from study_api.privacy_sanitizer import (
    BLOCK_COLOR,
    PrivacySanitizationError,
    PrivacySanitizer,
    SanitizerSignals,
    SensitiveRegion,
)


def _synthetic_png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (16, 12), (240, 200, 160)).save(output, format="PNG")
    return output.getvalue()


def test_sanitizer_removes_metadata_and_replaces_sensitive_pixels() -> None:
    source = _synthetic_png()
    signals = SanitizerSignals(
        regions=(
            SensitiveRegion(
                kind=SensitiveRegionKind.PHONE,
                x=2,
                y=3,
                width=5,
                height=4,
                confidence=0.99,
                source="rule",
            ),
        )
    )

    result = PrivacySanitizer().sanitize(source, "image/png", signals)

    assert result.metadata.safe_to_upload is True
    assert result.metadata.requires_confirmation is True
    assert result.metadata.sensitive_types == (SensitiveRegionKind.PHONE,)
    assert result.metadata.region_count == 1
    with Image.open(BytesIO(result.data)) as image:
        assert image.getexif() == {}
        assert image.getpixel((3, 4)) == BLOCK_COLOR
        assert image.getpixel((1, 2)) == BLOCK_COLOR
        assert image.getpixel((0, 0)) == (240, 200, 160)


def test_sanitizer_blocks_uncertain_or_unmaskable_visual_signals() -> None:
    result = PrivacySanitizer().sanitize(
        _synthetic_png(),
        "image/png",
        SanitizerSignals(
            face_detected=True,
            face_area_ratio=0.30,
            face_ambiguous=True,
            qr_detected=True,
            low_confidence=True,
        ),
    )

    assert result.metadata.safe_to_upload is False
    assert result.metadata.blocked_reasons == (
        "low_detection_confidence",
        "large_face",
        "ambiguous_face",
        "face_region_missing",
        "qr_region_missing",
    )
    assert result.metadata.region_count == 0


def test_sanitizer_does_not_mask_an_ordinary_math_image_without_signals() -> None:
    result = PrivacySanitizer().sanitize(_synthetic_png(), "image/png", SanitizerSignals())

    assert result.metadata.safe_to_upload is True
    assert result.metadata.sensitive_types == ()
    assert result.metadata.region_count == 0
    assert result.metadata.blocked_reasons == ()


def test_sanitizer_rejects_a_detector_region_outside_the_image() -> None:
    signals = SanitizerSignals(
        regions=(
            SensitiveRegion(
                kind=SensitiveRegionKind.SCHOOL,
                x=15,
                y=0,
                width=2,
                height=2,
                confidence=0.99,
                source="ocr",
            ),
        )
    )

    with pytest.raises(PrivacySanitizationError, match="outside image"):
        PrivacySanitizer().sanitize(_synthetic_png(), "image/png", signals)


def test_provider_neutral_question_contract_keeps_manual_gate() -> None:
    extraction = QuestionExtraction(
        subject="math",
        question_text="3/4 + 1/8",
        options=(),
        formulas=("3/4 + 1/8",),
        has_diagram=False,
        has_handwriting=False,
        confidence=0.91,
        question_region_count=1,
    )
    assert extraction.needs_confirmation is True
    assert (
        PrivacySanitization(
            sanitizer_version="privacy-sanitizer.synthetic-v1",
            safe_to_upload=False,
            sensitive_types=(),
            region_count=0,
            face_detected=False,
            qr_detected=False,
            barcode_detected=False,
            blocked_reasons=("low_detection_confidence",),
            sanitized_derivative_sha256="0" * 64,
        ).requires_confirmation
        is True
    )


def test_provider_neutral_question_contract_rejects_control_characters() -> None:
    with pytest.raises(ValueError, match="control"):
        QuestionExtraction(
            subject="math",
            question_text="bad\x00text",
            options=(),
            formulas=(),
            has_diagram=False,
            has_handwriting=False,
            confidence=0.1,
            question_region_count=0,
        )
