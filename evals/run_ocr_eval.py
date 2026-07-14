"""Run the fixed, repository-authored synthetic OCR contract evaluation.

This runner deliberately does not invoke PaddleOCR, MinIO, a network Provider,
or any image file. It evaluates the trust-boundary normalization that must hold
before OCR output can be persisted.
"""

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api/src"))

from study_api.domain.models import OcrResultStatus  # noqa: E402
from study_api.domain.ocr_result_repository import OcrResultDraft  # noqa: E402
from study_api.ocr_provider import OcrResultError, parse_paddle_text_result  # noqa: E402

FIXTURE = Path(__file__).with_name("fixtures") / "ocr_synthetic_v1.json"


def _check_case(case: dict[str, Any]) -> None:
    payload = case["payload"]
    expected_error = case.get("expected_error")
    try:
        parsed = parse_paddle_text_result(payload)
    except OcrResultError as error:
        if expected_error != type(error).__name__:
            raise AssertionError(f"unexpected error for case {case['id']}") from error
        return
    if expected_error is not None:
        raise AssertionError(f"case {case['id']} was accepted unexpectedly")

    expected = case["expected"]
    draft = OcrResultDraft.from_parse_result(parsed)
    actual = {
        "status": parsed.status,
        "candidate_count": len(parsed.candidates),
        "confidence": parsed.confidence,
        "low_confidence": parsed.low_confidence,
        "requires_manual_confirmation": draft.requires_manual_confirmation,
    }
    if actual != expected:
        raise AssertionError(f"contract mismatch for case {case['id']}")
    if draft.status is not OcrResultStatus(parsed.status):
        raise AssertionError(f"draft status mismatch for case {case['id']}")


def main() -> int:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cases = fixture["cases"]
    failures: list[str] = []
    for case in cases:
        try:
            _check_case(case)
        except AssertionError as error:
            failures.append(str(error))
    report = {
        "suite_id": fixture["suite_id"],
        "schema_version": fixture["schema_version"],
        "cases": len(cases),
        "passed": len(cases) - len(failures),
        "failed": len(failures),
        "provider_calls": fixture["source"]["provider_calls"],
        "status": "passed" if not failures else "failed",
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    if failures:
        for failure in failures:
            print(f"failure: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
