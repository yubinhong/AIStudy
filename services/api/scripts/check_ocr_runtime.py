"""Check the locked Ubuntu CPU OCR runtime without downloading models or reading images."""

import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from study_api.ocr_runtime import run_preflight  # noqa: E402


def main() -> int:
    model_root = os.environ.get("PADDLE_MODEL_ROOT")
    result = run_preflight(
        model_root=Path(model_root) if model_root else None,
        allow_locked_container=os.environ.get("STUDY_OCR_CONTAINER_RUNTIME") == "true",
    )
    print(json.dumps(asdict(result), ensure_ascii=True, sort_keys=True))
    return 0 if result.status == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
