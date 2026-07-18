"""Delete expired private media and short-lived data export snapshots."""

from __future__ import annotations

import json
import os
import sys
import time

from study_api.domain.insights_repository import PostgresInsightsRepository
from study_api.domain.sql_capture_repository import PostgresCaptureRepository
from study_api.media_lifecycle import CaptureMediaCleanup
from study_api.object_storage import ObjectStorageConfig, S3ObjectStorage


def _poll_interval() -> float:
    raw = os.getenv("DATA_LIFECYCLE_POLL_INTERVAL_SECONDS", "300")
    try:
        return max(30.0, min(float(raw), 3600.0))
    except ValueError:
        return 300.0


def run_once() -> dict[str, int]:
    captures = PostgresCaptureRepository()
    insights = PostgresInsightsRepository()
    try:
        media = CaptureMediaCleanup(
            captures,
            S3ObjectStorage(ObjectStorageConfig.from_environment()),
        ).run_once()
        return {
            "media_claimed": media.claimed,
            "media_deleted": media.deleted,
            "media_failed": media.failed,
            "exports_deleted": insights.cleanup_expired_exports(),
        }
    finally:
        captures.close()
        insights.close()


def main(args: list[str] | None = None) -> int:
    effective_args = args if args is not None else sys.argv[1:]
    watch = "--watch" in effective_args
    while True:
        try:
            summary = run_once()
            print(json.dumps({"event": "data_lifecycle.completed", **summary}), flush=True)
        except Exception:  # noqa: BLE001 -- retry without leaking storage/DB details.
            print(
                json.dumps({"event": "data_lifecycle.failed", "retryable": True}),
                flush=True,
            )
            if not watch:
                return 1
        if not watch:
            return 0
        time.sleep(_poll_interval())


if __name__ == "__main__":
    raise SystemExit(main())
