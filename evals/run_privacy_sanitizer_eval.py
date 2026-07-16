"""Run the fixed, no-network PrivacySanitizer synthetic evaluation."""

import json
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "services/api/src"))

from study_api.privacy_sanitizer import (  # noqa: E402
    PrivacySanitizer,
    SanitizerSignals,
    SensitiveRegion,
)

FIXTURE = Path(__file__).with_name("fixtures") / "privacy_sanitizer_synthetic_v1.json"


def _synthetic_png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (16, 12), (240, 200, 160)).save(output, format="PNG")
    return output.getvalue()


def main() -> int:
    fixture = json.loads(FIXTURE.read_text())
    passed = 0
    for case in fixture["cases"]:
        signals = SanitizerSignals(
            regions=tuple(SensitiveRegion.model_validate(region) for region in case["regions"]),
            face_detected=case.get("face_detected", False),
            face_area_ratio=case.get("face_area_ratio", 0.0),
            face_ambiguous=case.get("face_ambiguous", False),
            qr_detected=case.get("qr_detected", False),
            barcode_detected=case.get("barcode_detected", False),
            low_confidence=case.get("low_confidence", False),
            crop_incomplete=case.get("crop_incomplete", False),
        )
        result = PrivacySanitizer().sanitize(_synthetic_png(), "image/png", signals)
        if (
            result.metadata.safe_to_upload == case["expected_safe_to_upload"]
            and result.metadata.region_count == case["expected_region_count"]
            and result.metadata.requires_confirmation
            and len(result.data) > 0
        ):
            passed += 1

    report = {
        "cases": len(fixture["cases"]),
        "failed": len(fixture["cases"]) - passed,
        "passed": passed,
        "provider_calls": False,
        "schema_version": fixture["schema_version"],
        "status": "passed" if passed == len(fixture["cases"]) else "failed",
        "suite_id": fixture["suite_id"],
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
