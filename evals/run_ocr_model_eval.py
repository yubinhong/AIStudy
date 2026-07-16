"""Run the locked local CPU OCR model against generated synthetic math images.

The script never accepts an image path. Every input is rendered in memory from
the repository manifest, and output contains only aggregate metrics.
"""

from __future__ import annotations

import json
import os
import sys
import time
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api/src"))

from study_api.capture_media import SafeCaptureInput  # noqa: E402
from study_api.image_safety import normalize_image_for_ocr  # noqa: E402
from study_api.ocr_provider import LocalPaddleOcrAdapter, PaddleModelPaths  # noqa: E402
from study_api.ocr_runtime import run_preflight  # noqa: E402

FIXTURE = Path(__file__).with_name("ocr_model_synthetic_v1.json")


def _font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ):
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size=64)
    return ImageFont.load_default()


def _synthetic_capture(text: str) -> SafeCaptureInput:
    image = Image.new("RGB", (1400, 220), color="white")
    ImageDraw.Draw(image).text((60, 70), text, fill="black", font=_font())
    output = BytesIO()
    image.save(output, format="PNG")
    normalized = normalize_image_for_ocr(output.getvalue(), "image/png")
    return SafeCaptureInput(data=normalized.data, metadata=normalized.metadata)


def _recognized(candidates: tuple[Any, ...], expected_terms: list[str]) -> bool:
    text = "".join(str(candidate.text) for candidate in candidates)
    compact = "".join(character for character in text if character.isalnum())
    return all(term in compact for term in expected_terms)


def run_eval(model_root: Path) -> dict[str, Any]:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    adapter = LocalPaddleOcrAdapter(PaddleModelPaths(model_root))
    cases: list[dict[str, Any]] = []
    for case in fixture["cases"]:
        started = time.perf_counter()
        try:
            capture = _synthetic_capture(case["text"])
            if case.get("kind") == "formula":
                result = adapter.run_formula_ocr(capture)
            else:
                result = adapter.run_text_ocr(capture)
            recognized = _recognized(result.candidates, case["expected_terms"])
            status = "passed" if recognized else "mismatch"
        except Exception:  # noqa: BLE001 -- aggregate report must not expose Provider details.
            recognized = False
            status = "error"
        cases.append(
            {
                "id": case["id"],
                "kind": case.get("kind", "text"),
                "topic": case["topic"],
                "status": status,
                "recognized": recognized,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        )
    passed = sum(case["status"] == "passed" for case in cases)
    return {
        "suite_id": fixture["suite_id"],
        "model": fixture["model"],
        "device": fixture["device"],
        "cases": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "provider_calls": True,
        "status": "passed" if passed == len(cases) else "failed",
        "case_metrics": cases,
    }


def main() -> int:
    model_root = os.environ.get("PADDLE_MODEL_ROOT")
    preflight = run_preflight(
        model_root=Path(model_root) if model_root else None,
        allow_locked_container=os.environ.get("STUDY_OCR_CONTAINER_RUNTIME") == "true",
    )
    if preflight.status != "ready":
        print(
            json.dumps(
                {"status": "blocked", "failures": preflight.failures}, ensure_ascii=True
            )
        )
        return 2
    report = run_eval(Path(model_root))
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
