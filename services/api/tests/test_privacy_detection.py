from study_api.privacy_detection import LocalPrivacyDetector, OcrTextBox
from study_api.privacy_models import SensitiveRegionKind


def test_detector_masks_sensitive_label_and_adjacent_value_without_returning_text() -> None:
    signals = LocalPrivacyDetector().detect(
        [
            OcrTextBox(text="姓名", x=1, y=1, width=2, height=2, confidence=0.99),
            OcrTextBox(text="小明", x=5, y=1, width=3, height=2, confidence=0.95),
        ]
    )

    assert [region.kind for region in signals.regions] == [
        SensitiveRegionKind.NAME,
        SensitiveRegionKind.NAME,
    ]
    assert not hasattr(signals, "text")


def test_detector_uses_rule_patterns_for_phone_but_not_ordinary_math_numbers() -> None:
    detector = LocalPrivacyDetector()

    phone = detector.detect(
        [OcrTextBox(text="13812345678", x=1, y=1, width=8, height=2, confidence=0.99)]
    )
    math = detector.detect(
        [OcrTextBox(text="3/4 + 1/8", x=1, y=1, width=8, height=2, confidence=0.99)]
    )

    assert [region.kind for region in phone.regions] == [SensitiveRegionKind.PHONE]
    assert math.regions == ()


def test_detector_marks_low_confidence_without_guessing_a_sensitive_type() -> None:
    signals = LocalPrivacyDetector().detect(
        [OcrTextBox(text="小明", x=1, y=1, width=3, height=2, confidence=0.4)]
    )

    assert signals.regions == ()
    assert signals.low_confidence is True
