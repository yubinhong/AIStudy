"""Run one queued local OCR job and exit with a stable status code."""

from study_api.ocr_worker import main

if __name__ == "__main__":
    raise SystemExit(main())
