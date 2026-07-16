"""Run one real NewAPI vision job with a synthetic image and clean it up.

This is an environment eval, not a production endpoint. It intentionally uses
the seeded synthetic child, an in-memory generated PNG, and removes every
database row created by the run in a ``finally`` block. No API key or raw
Provider response is printed.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import date
from hashlib import sha256
from io import BytesIO
from typing import Any
from uuid import UUID

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import MetaData, delete

from study_api.domain.models import (
    ConfirmCaptureUploadRequest,
    CreateCaptureRequest,
    CreateTaskRequest,
    StartStudySessionRequest,
    Subject,
)
from study_api.domain.question_extraction_repository import (
    PostgresQuestionExtractionRepository,
)
from study_api.domain.repository import InMemoryProfileRepository
from study_api.domain.sql_capture_repository import PostgresCaptureRepository
from study_api.domain.sql_learning_repository import PostgresLearningRepository
from study_api.image_analysis_jobs import ImageAnalysisJobStatus, PostgresImageAnalysisJobRepository
from study_api.image_analysis_worker import ImageAnalysisDispatcher, NewApiImageAnalysisRunner
from study_api.newapi_provider import NewApiConfig, NewApiVisionProvider
from study_api.object_storage import ObjectStorageConfig, ObjectStorageError, S3ObjectStorage
from study_api.privacy_models import PrivacySanitization, StartImageAnalysisRequest

HOUSEHOLD_ID = UUID("00000000-0000-0000-0000-000000000001")
CHILD_ID = UUID("00000000-0000-0000-0000-000000000101")


def _synthetic_png() -> bytes:
    image = Image.new("RGB", (1600, 500), "white")
    draw = ImageDraw.Draw(image)
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 92)
    except OSError:
        font = ImageFont.load_default()
    draw.text((80, 110), "Math: 3/4 + 1/8 = ?", fill="black", font=font)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _upload(storage: S3ObjectStorage, object_key: str, data: bytes) -> None:
    signed = storage.create_put_url(object_key, "image/png", len(data))
    request = urllib.request.Request(
        signed.url,
        data=data,
        headers={"Content-Type": "image/png", "Content-Length": str(len(data))},
        method="PUT",
    )
    with urllib.request.urlopen(request, timeout=30):
        pass


def _cleanup(
    engine: Any,
    *,
    task_id: UUID | None,
    session_id: UUID | None,
    capture_id: UUID | None,
    job_id: UUID | None,
    extraction_id: UUID | None,
) -> None:
    metadata = MetaData()
    metadata.reflect(
        bind=engine,
        only=(
            "verified_questions",
            "question_extractions",
            "image_analysis_jobs",
            "capture_corrections",
            "captures",
            "attempts",
            "study_sessions",
            "study_tasks",
            "idempotency_records",
            "audit_events",
        ),
    )
    with engine.begin() as connection:
        if extraction_id is not None:
            connection.execute(
                delete(metadata.tables["verified_questions"]).where(
                    metadata.tables["verified_questions"].c.extraction_id == extraction_id
                )
            )
            connection.execute(
                delete(metadata.tables["question_extractions"]).where(
                    metadata.tables["question_extractions"].c.id == extraction_id
                )
            )
        if job_id is not None:
            connection.execute(
                delete(metadata.tables["image_analysis_jobs"]).where(
                    metadata.tables["image_analysis_jobs"].c.id == job_id
                )
            )
        if capture_id is not None:
            connection.execute(
                delete(metadata.tables["capture_corrections"]).where(
                    metadata.tables["capture_corrections"].c.capture_id == capture_id
                )
            )
            connection.execute(
                delete(metadata.tables["captures"]).where(
                    metadata.tables["captures"].c.id == capture_id
                )
            )
        if session_id is not None:
            connection.execute(
                delete(metadata.tables["attempts"]).where(
                    metadata.tables["attempts"].c.session_id == session_id
                )
            )
            connection.execute(
                delete(metadata.tables["study_sessions"]).where(
                    metadata.tables["study_sessions"].c.id == session_id
                )
            )
        if task_id is not None:
            connection.execute(
                delete(metadata.tables["study_tasks"]).where(
                    metadata.tables["study_tasks"].c.id == task_id
                )
            )
        resource_ids = [value for value in (task_id, session_id, capture_id) if value is not None]
        if resource_ids:
            connection.execute(
                delete(metadata.tables["idempotency_records"]).where(
                    metadata.tables["idempotency_records"].c.resource_id.in_(resource_ids)
                )
            )
            connection.execute(
                delete(metadata.tables["audit_events"]).where(
                    metadata.tables["audit_events"].c.resource_id.in_(resource_ids)
                )
            )


def main() -> int:
    config = NewApiConfig.from_environment()
    if not config.enabled:
        raise RuntimeError("STUDY_NEWAPI_ENABLED must be true")

    image = _synthetic_png()
    digest = sha256(image).hexdigest()
    profiles = InMemoryProfileRepository()
    learning = PostgresLearningRepository(profiles)
    captures = PostgresCaptureRepository()
    jobs = PostgresImageAnalysisJobRepository()
    extractions = PostgresQuestionExtractionRepository()
    storage = S3ObjectStorage(ObjectStorageConfig.from_environment())
    task_id: UUID | None = None
    session_id: UUID | None = None
    capture_id: UUID | None = None
    job_id: UUID | None = None
    extraction_id: UUID | None = None
    object_key: str | None = None
    output: dict[str, object] = {"provider_enabled": True, "model": config.vision_model}
    try:
        task, _ = learning.create_task(
            HOUSEHOLD_ID,
            CreateTaskRequest(
                child_id=CHILD_ID,
                title="Synthetic NewAPI live eval",
                subject=Subject.MATH,
                scheduled_for=date.today(),
            ),
            "newapi-live-eval-task",
        )
        task_id = task.id
        session, _ = learning.start_session(
            HOUSEHOLD_ID,
            task.id,
            CHILD_ID,
            StartStudySessionRequest(expected_task_version=1),
            "newapi-live-eval-session",
        )
        session_id = session.id
        pending, _ = captures.begin_capture_upload(
            HOUSEHOLD_ID,
            session.id,
            CHILD_ID,
            CreateCaptureRequest(
                media_type="image/png", byte_size=len(image), content_sha256=digest
            ),
            "newapi-live-eval-capture",
        )
        capture_id = pending.capture.id
        object_key = pending.object_key
        storage.ensure_bucket()
        _upload(storage, object_key, image)
        storage.validate_uploaded_object(object_key, "image/png", len(image), digest)
        captures.confirm_capture_upload(
            HOUSEHOLD_ID,
            capture_id,
            CHILD_ID,
            ConfirmCaptureUploadRequest(expected_capture_version=1),
            "newapi-live-eval-confirm",
        )
        request = StartImageAnalysisRequest(
            expected_capture_version=2,
            user_confirmed=True,
            sanitization=PrivacySanitization(
                sanitizer_version="live-eval-synthetic-v1",
                safe_to_upload=True,
                sensitive_types=(),
                region_count=0,
                face_detected=False,
                qr_detected=False,
                barcode_detected=False,
                blocked_reasons=(),
                sanitized_derivative_sha256=digest,
            ),
        )
        job, _ = jobs.create(
            HOUSEHOLD_ID,
            capture_id,
            CHILD_ID,
            "newapi-live-eval-analysis",
            request,
            status=ImageAnalysisJobStatus.QUEUED,
            error_code=None,
        )
        job_id = job.id
        dispatcher = ImageAnalysisDispatcher(
            jobs,
            NewApiImageAnalysisRunner(
                captures,
                storage,
                NewApiVisionProvider(config),
                extractions,
            ),
        )
        dispatch = dispatcher.run_once()
        final_job = jobs.get(HOUSEHOLD_ID, capture_id, CHILD_ID, job.id)
        output.update({"job_status": final_job.status.value, "job_attempt": final_job.attempt})
        if dispatch is None or dispatch.status != "succeeded" or final_job.extraction_id is None:
            output["error_code"] = final_job.error_code
            output["dispatch_status"] = dispatch.status if dispatch is not None else None
            print(json.dumps(output, ensure_ascii=True, sort_keys=True))
            raise RuntimeError("live NewAPI image analysis did not succeed")
        extraction_id = final_job.extraction_id
        record = extractions.get(HOUSEHOLD_ID, capture_id, extraction_id, CHILD_ID)
        output.update(
            {
                "extraction_id_present": True,
                "subject": record.extraction.subject,
                "confidence": record.extraction.confidence,
                "question_text_length": len(record.extraction.question_text),
                "needs_confirmation": record.extraction.needs_confirmation,
            }
        )
        try:
            storage.read_object(object_key, max_bytes=len(image))
        except ObjectStorageError:
            output["derivative_deleted"] = True
        else:
            output["derivative_deleted"] = False
            raise RuntimeError("sanitized derivative was not deleted")
        print(json.dumps(output, ensure_ascii=True, sort_keys=True))
        return 0
    finally:
        _cleanup(
            learning.engine,
            task_id=task_id,
            session_id=session_id,
            capture_id=capture_id,
            job_id=job_id,
            extraction_id=extraction_id,
        )
        if object_key is not None:
            try:
                storage.delete_object(object_key)
            except Exception:
                pass
        learning.close()
        captures.close()
        jobs.close()
        extractions.close()


if __name__ == "__main__":
    raise SystemExit(main())
