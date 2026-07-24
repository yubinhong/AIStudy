import base64
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

import pytest
from auth_helpers import session_headers
from fastapi.testclient import TestClient
from sqlalchemy import select

from study_api.domain.models import Capture, CaptureStatus, OcrMode, OcrResultStatus
from study_api.domain.ocr_result_repository import (
    OcrCandidateDraft,
    OcrResultDraft,
    PostgresOcrResultRepository,
)
from study_api.domain.repository import InMemoryProfileRepository
from study_api.domain.sql_capture_repository import PostgresCaptureRepository
from study_api.domain.sql_learning_repository import PostgresLearningRepository
from study_api.image_analysis_jobs import PostgresImageAnalysisJobRepository
from study_api.main import create_app
from study_api.media_lifecycle import (
    CaptureMediaCleanup,
    CaptureObjectCascadeDeletion,
    DeletionStatus,
    RetentionClass,
)
from study_api.object_storage import (
    CaptureObjectStorage,
    ObjectStorageConfig,
    ObjectStorageError,
    PresignedUpload,
    S3ObjectStorage,
)
from study_api.ocr_jobs import (
    LocalOcrDispatcher,
    OcrJobIdempotencyConflictError,
    OcrJobStatus,
    PostgresOcrJobQueue,
)
from study_api.ocr_provider import OcrParseResult, parse_paddle_text_result
from study_api.ocr_service import LocalOcrJob

HOUSEHOLD_A = "00000000-0000-0000-0000-000000000001"
CHILD_A = "00000000-0000-0000-0000-000000000101"

pytestmark = pytest.mark.integration


class FakeObjectStorage:
    def __init__(self) -> None:
        self.object_key: str | None = None
        self.uploaded: tuple[str, int] | None = None
        self.data: bytes | None = None
        self.deleted: list[str] = []

    def ensure_bucket(self) -> None:
        return None

    def create_put_url(self, object_key: str, content_type: str, byte_size: int) -> PresignedUpload:
        self.object_key = object_key
        return PresignedUpload(url="https://synthetic.invalid/upload", expires_at=datetime.now(UTC))

    def upload(self, content_type: str, byte_size: int, data: bytes | None = None) -> None:
        self.uploaded = (content_type, byte_size)
        self.data = data

    def read_object(self, object_key: str, max_bytes: int) -> bytes:
        assert object_key == self.object_key
        assert self.data is not None
        assert len(self.data) <= max_bytes
        return self.data

    def validate_uploaded_object(
        self, object_key: str, content_type: str, byte_size: int, content_sha256: str
    ) -> None:
        if object_key != self.object_key or self.uploaded != (content_type, byte_size):
            raise ObjectStorageError("synthetic object is unavailable")

    def delete_object(self, object_key: str) -> None:
        self.deleted.append(object_key)


def _headers(
    client: TestClient, role: str = "parent", child_id: str | None = None
) -> dict[str, str]:
    return session_headers(client, role=role, child_id=child_id)


def _client(
    object_storage: CaptureObjectStorage | None = None,
    ocr_job_queue: PostgresOcrJobQueue | None = None,
    ocr_result_repository: PostgresOcrResultRepository | None = None,
    image_analysis_repository: PostgresImageAnalysisJobRepository | None = None,
) -> tuple[TestClient, PostgresLearningRepository, PostgresCaptureRepository]:
    profiles = InMemoryProfileRepository()
    learning = PostgresLearningRepository(profiles)
    captures = PostgresCaptureRepository()
    return (
        TestClient(
            create_app(
                profiles,
                learning,
                captures,
                object_storage,
                ocr_job_queue,
                ocr_result_repository,
                image_analysis_repository,
            )
        ),
        learning,
        captures,
    )


class SyntheticOcrAdapter:
    def run_text_ocr(self, capture: object, *, confidence_threshold: float = 0.8) -> OcrParseResult:
        assert confidence_threshold == 0.8
        return parse_paddle_text_result(
            {"rec_texts": ["synthetic 3 + 4"], "rec_scores": [0.93]},
            confidence_threshold=confidence_threshold,
        )


def _session(client: TestClient) -> str:
    task = client.post(
        f"/households/{HOUSEHOLD_A}/tasks",
        headers={**_headers(client), "Idempotency-Key": f"pg-capture-task-{uuid4()}"},
        json={
            "child_id": CHILD_A,
            "title": "Synthetic PostgreSQL capture task",
            "subject": "math",
            "scheduled_for": date(2026, 7, 13).isoformat(),
        },
    ).json()
    response = client.post(
        f"/households/{HOUSEHOLD_A}/tasks/{task['id']}/sessions",
        headers={
            **_headers(client, "child", CHILD_A),
            "Idempotency-Key": f"pg-capture-session-{uuid4()}",
        },
        json={"expected_task_version": task["version"]},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_postgresql_capture_correction_is_transactional_and_idempotent() -> None:
    client, learning, repository = _client()
    try:
        session_id = _session(client)
        capture_response = client.post(
            f"/households/{HOUSEHOLD_A}/sessions/{session_id}/captures",
            headers={
                **_headers(client, "child", CHILD_A),
                "Idempotency-Key": f"pg-capture-create-{uuid4()}",
            },
            json={
                "media_type": "image/png",
                "byte_size": 2048,
                "content_sha256": sha256(b"synthetic-postgres-capture").hexdigest(),
            },
        )
        assert capture_response.status_code == 201
        capture = capture_response.json()
        headers = {
            **_headers(client, "child", CHILD_A),
            "Idempotency-Key": f"pg-capture-correction-{uuid4()}",
        }
        payload = {"expected_capture_version": 1, "corrected_text": "synthetic corrected text"}
        first = client.post(
            f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/corrections",
            headers=headers,
            json=payload,
        )
        replay = client.post(
            f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/corrections",
            headers=headers,
            json=payload,
        )

        assert first.status_code == 201
        assert replay.status_code == 200
        with repository.engine.connect() as connection:
            corrections = (
                connection.execute(
                    select(repository._corrections).where(
                        repository._corrections.c.capture_id == UUID(capture["id"])
                    )
                )
                .mappings()
                .all()
            )
            audits = (
                connection.execute(
                    select(repository._audits).where(
                        repository._audits.c.resource_id == UUID(capture["id"])
                    )
                )
                .mappings()
                .all()
            )
        assert len(corrections) == 1
        assert corrections[0]["corrected_text"] == "synthetic corrected text"
        assert {audit["event_name"] for audit in audits} == {"capture_created", "capture_corrected"}
    finally:
        learning.close()
        repository.close()


def test_postgresql_ocr_candidate_confirmation_reuses_capture_correction_transaction() -> None:
    profiles = InMemoryProfileRepository()
    learning = PostgresLearningRepository(profiles)
    repository = PostgresCaptureRepository()
    ocr_results = PostgresOcrResultRepository()
    client = TestClient(
        create_app(
            profiles,
            learning,
            repository,
            ocr_result_repository=ocr_results,
        )
    )
    try:
        session_id = _session(client)
        capture_response = client.post(
            f"/households/{HOUSEHOLD_A}/sessions/{session_id}/captures",
            headers={
                **_headers(client, "child", CHILD_A),
                "Idempotency-Key": f"pg-ocr-confirm-create-{uuid4()}",
            },
            json={
                "media_type": "image/png",
                "byte_size": 2048,
                "content_sha256": sha256(b"synthetic-ocr-confirmation").hexdigest(),
            },
        )
        assert capture_response.status_code == 201
        capture = capture_response.json()
        result, _ = ocr_results.create_result(
            UUID(HOUSEHOLD_A),
            UUID(capture["id"]),
            UUID(CHILD_A),
            OcrResultDraft(
                provider="local_paddleocr",
                model="PP-OCRv6_medium",
                model_version="synthetic",
                schema_version="ocr-result.v1",
                confidence=0.93,
                status=OcrResultStatus.CANDIDATE,
                candidates=(OcrCandidateDraft(text="synthetic 9 + 6", confidence=0.93),),
            ),
            f"pg-ocr-result-{uuid4()}",
        )
        _, candidates = ocr_results.get_result(UUID(HOUSEHOLD_A), result.id, UUID(CHILD_A))
        path = (
            f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/ocr-results/"
            f"{result.id}/confirmations"
        )
        headers = {
            **_headers(client, "child", CHILD_A),
            "Idempotency-Key": f"pg-ocr-confirm-{uuid4()}",
        }
        payload = {
            "expected_capture_version": capture["version"],
            "candidate_id": str(candidates[0].id),
        }

        first = client.post(path, headers=headers, json=payload)
        replay = client.post(path, headers=headers, json=payload)

        assert first.status_code == 201
        assert first.json()["corrected_text"] == "synthetic 9 + 6"
        assert replay.status_code == 200
        with repository.engine.connect() as connection:
            correction_rows = (
                connection.execute(
                    select(repository._corrections).where(
                        repository._corrections.c.capture_id == UUID(capture["id"])
                    )
                )
                .mappings()
                .all()
            )
        assert len(correction_rows) == 1
        assert correction_rows[0]["corrected_text"] == "synthetic 9 + 6"
        confirmed_result, confirmed_candidates = ocr_results.get_result(
            UUID(HOUSEHOLD_A), result.id, UUID(CHILD_A)
        )
        assert confirmed_result.requires_manual_confirmation is True
        assert confirmed_candidates[0].text == "synthetic 9 + 6"
    finally:
        ocr_results.close()
        learning.close()
        repository.close()


def test_postgresql_capture_upload_keeps_object_key_internal_and_confirms_once() -> None:
    storage = FakeObjectStorage()
    client, learning, repository = _client(storage)
    try:
        session_id = _session(client)
        upload_response = client.post(
            f"/households/{HOUSEHOLD_A}/sessions/{session_id}/capture-uploads",
            headers={
                **_headers(client, "child", CHILD_A),
                "Idempotency-Key": f"pg-capture-upload-{uuid4()}",
            },
            json={
                "media_type": "image/png",
                "byte_size": 2048,
                "content_sha256": sha256(b"synthetic-postgres-upload").hexdigest(),
            },
        )
        assert upload_response.status_code == 201
        upload = upload_response.json()
        capture = upload["capture"]
        assert "object_key" not in str(upload)

        storage.upload("image/png", 2048)
        confirmation = client.post(
            f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/upload-confirmations",
            headers={
                **_headers(client, "child", CHILD_A),
                "Idempotency-Key": f"pg-capture-confirm-{uuid4()}",
            },
            json={"expected_capture_version": capture["version"]},
        )
        assert confirmation.status_code == 201
        assert confirmation.json()["status"] == "needs_correction"

        with repository.engine.connect() as connection:
            stored = (
                connection.execute(
                    select(repository._captures).where(
                        repository._captures.c.id == UUID(capture["id"])
                    )
                )
                .mappings()
                .one()
            )
            audits = (
                connection.execute(
                    select(repository._audits).where(
                        repository._audits.c.resource_id == UUID(capture["id"])
                    )
                )
                .mappings()
                .all()
            )
        assert stored["object_key"] == storage.object_key
        assert {audit["event_name"] for audit in audits} == {
            "capture_upload_requested",
            "capture_upload_confirmed",
        }
    finally:
        learning.close()
        repository.close()


def test_postgresql_image_analysis_receipt_is_household_scoped_and_idempotent() -> None:
    storage = FakeObjectStorage()
    image_analysis = PostgresImageAnalysisJobRepository()
    client, learning, repository = _client(storage, image_analysis_repository=image_analysis)
    try:
        session_id = _session(client)
        content_hash = sha256(b"synthetic-sanitized-derivative").hexdigest()
        upload_response = client.post(
            f"/households/{HOUSEHOLD_A}/sessions/{session_id}/capture-uploads",
            headers={
                **_headers(client, "child", CHILD_A),
                "Idempotency-Key": f"pg-image-analysis-upload-{uuid4()}",
            },
            json={
                "media_type": "image/png",
                "byte_size": 2048,
                "content_sha256": content_hash,
            },
        )
        assert upload_response.status_code == 201
        capture = upload_response.json()["capture"]
        storage.upload("image/png", 2048)
        confirmation = client.post(
            f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/upload-confirmations",
            headers={
                **_headers(client, "child", CHILD_A),
                "Idempotency-Key": f"pg-image-analysis-confirm-{uuid4()}",
            },
            json={"expected_capture_version": capture["version"]},
        )
        assert confirmation.status_code == 201
        confirmed = confirmation.json()
        request_body = {
            "expected_capture_version": confirmed["version"],
            "sanitization": {
                "schema_version": "privacy-sanitization.v1",
                "sanitizer_version": "synthetic-test",
                "safe_to_upload": True,
                "requires_confirmation": True,
                "sensitive_types": [],
                "region_count": 0,
                "face_detected": False,
                "qr_detected": False,
                "barcode_detected": False,
                "blocked_reasons": [],
                "sanitized_derivative_sha256": content_hash,
            },
            "user_confirmed": True,
        }
        headers = {
            **_headers(client, "child", CHILD_A),
            "Idempotency-Key": "pg-image-analysis-start",
        }
        first = client.post(
            f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/image-analysis-jobs",
            headers=headers,
            json=request_body,
        )
        replay = client.post(
            f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/image-analysis-jobs",
            headers=headers,
            json=request_body,
        )
        assert first.status_code == 202
        assert first.json()["error_code"] == "provider_not_enabled"
        assert replay.status_code == 200
        assert replay.headers["Idempotency-Replayed"] == "true"

        read = client.get(
            f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/image-analysis-jobs/{first.json()['id']}",
            headers=_headers(client, "child", CHILD_A),
        )
        assert read.status_code == 200
        assert read.json()["sanitized_derivative_sha256"] == content_hash
    finally:
        image_analysis.close()
        learning.close()
        repository.close()


def test_postgresql_minio_capture_upload_confirmation_is_end_to_end_synthetic() -> None:
    storage = S3ObjectStorage(
        ObjectStorageConfig(
            endpoint_url="http://127.0.0.1:9000",
            bucket="study-captures-local",
            access_key_id="minio_local",
            secret_access_key="minio_local_only",
        )
    )
    storage.ensure_bucket()
    client, learning, repository = _client(storage)
    object_key: str | None = None
    content = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    try:
        session_id = _session(client)
        upload_response = client.post(
            f"/households/{HOUSEHOLD_A}/sessions/{session_id}/capture-uploads",
            headers={
                **_headers(client, "child", CHILD_A),
                "Idempotency-Key": f"pg-minio-capture-upload-{uuid4()}",
            },
            json={
                "media_type": "image/png",
                "byte_size": len(content),
                "content_sha256": sha256(content).hexdigest(),
            },
        )
        assert upload_response.status_code == 201
        upload = upload_response.json()
        assert "object_key" not in str(upload)
        request = Request(
            upload["upload_url"],
            data=content,
            method="PUT",
            headers={"Content-Type": "image/png"},
        )
        with urlopen(request, timeout=10) as response:  # noqa: S310 -- URL is server-generated.
            assert response.status in {200, 204}

        capture_id = UUID(upload["capture"]["id"])
        with repository.engine.connect() as connection:
            object_key = connection.execute(
                select(repository._captures.c.object_key).where(
                    repository._captures.c.id == capture_id
                )
            ).scalar_one()
        confirmation = client.post(
            f"/households/{HOUSEHOLD_A}/captures/{capture_id}/upload-confirmations",
            headers={
                **_headers(client, "child", CHILD_A),
                "Idempotency-Key": f"pg-minio-capture-confirm-{uuid4()}",
            },
            json={"expected_capture_version": upload["capture"]["version"]},
        )
        assert confirmation.status_code == 201
        assert confirmation.json()["status"] == "needs_correction"
    finally:
        if object_key is not None:
            storage.delete_object(object_key)
        learning.close()
        repository.close()


def test_postgresql_minio_ocr_worker_pipeline_is_visible_to_child_routes() -> None:
    storage = S3ObjectStorage(
        ObjectStorageConfig(
            endpoint_url="http://127.0.0.1:9000",
            bucket="study-captures-local",
            access_key_id="minio_local",
            secret_access_key="minio_local_only",
        )
    )
    storage.ensure_bucket()
    queue = PostgresOcrJobQueue()
    ocr_results = PostgresOcrResultRepository()
    client, learning, repository = _client(storage, queue, ocr_results)
    object_key: str | None = None
    content = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    try:
        session_id = _session(client)
        upload_response = client.post(
            f"/households/{HOUSEHOLD_A}/sessions/{session_id}/capture-uploads",
            headers={
                **_headers(client, "child", CHILD_A),
                "Idempotency-Key": f"pg-minio-ocr-upload-{uuid4()}",
            },
            json={
                "media_type": "image/png",
                "byte_size": len(content),
                "content_sha256": sha256(content).hexdigest(),
            },
        )
        assert upload_response.status_code == 201
        upload = upload_response.json()
        request = Request(
            upload["upload_url"],
            data=content,
            method="PUT",
            headers={"Content-Type": "image/png"},
        )
        with urlopen(request, timeout=10) as response:  # noqa: S310 -- URL is server-generated.
            assert response.status in {200, 204}

        capture_id = UUID(upload["capture"]["id"])
        with repository.engine.connect() as connection:
            object_key = connection.execute(
                select(repository._captures.c.object_key).where(
                    repository._captures.c.id == capture_id
                )
            ).scalar_one()
        confirmation = client.post(
            f"/households/{HOUSEHOLD_A}/captures/{capture_id}/upload-confirmations",
            headers={
                **_headers(client, "child", CHILD_A),
                "Idempotency-Key": f"pg-minio-ocr-confirm-{uuid4()}",
            },
            json={"expected_capture_version": upload["capture"]["version"]},
        )
        assert confirmation.status_code == 201

        enqueue = client.post(
            f"/households/{HOUSEHOLD_A}/captures/{capture_id}/ocr-jobs",
            headers={
                **_headers(client, "child", CHILD_A),
                "Idempotency-Key": f"pg-minio-ocr-job-{uuid4()}",
            },
        )
        assert enqueue.status_code == 202
        job = enqueue.json()
        job_path = f"/households/{HOUSEHOLD_A}/captures/{capture_id}/ocr-jobs/{job['id']}"
        assert (
            client.get(job_path, headers=_headers(client, "child", CHILD_A)).json()["status"]
            == "queued"
        )

        runner = LocalOcrJob(repository, storage, SyntheticOcrAdapter(), ocr_results)
        outcome = LocalOcrDispatcher(queue, runner).run_once()

        assert outcome is not None
        assert outcome.status is OcrJobStatus.SUCCEEDED
        assert outcome.result_id is not None
        completed = client.get(job_path, headers=_headers(client, "child", CHILD_A)).json()
        assert completed["status"] == "succeeded"
        assert completed["result_id"] == str(outcome.result_id)
        result = client.get(
            f"/households/{HOUSEHOLD_A}/captures/{capture_id}/ocr-results/{outcome.result_id}",
            headers=_headers(client, "child", CHILD_A),
        )
        assert result.status_code == 200
        assert result.json()["candidates"][0]["text"] == "synthetic 3 + 4"
        assert result.json()["result"]["requires_manual_confirmation"] is True
    finally:
        if object_key is not None:
            storage.delete_object(object_key)
        ocr_results.close()
        queue.close()
        learning.close()
        repository.close()


def test_postgresql_capture_cleanup_claims_expired_object_and_records_audit() -> None:
    storage = FakeObjectStorage()
    client, learning, repository = _client(storage)
    try:
        session_id = _session(client)
        upload_response = client.post(
            f"/households/{HOUSEHOLD_A}/sessions/{session_id}/capture-uploads",
            headers={
                **_headers(client, "child", CHILD_A),
                "Idempotency-Key": f"pg-cleanup-upload-{uuid4()}",
            },
            json={
                "media_type": "image/jpeg",
                "byte_size": 1024,
                "content_sha256": sha256(b"synthetic-cleanup").hexdigest(),
            },
        )
        assert upload_response.status_code == 201
        capture_id = UUID(upload_response.json()["capture"]["id"])
        with repository.engine.begin() as connection:
            connection.execute(
                repository._captures.update()
                .where(repository._captures.c.id == capture_id)
                .values(expires_at=datetime(2026, 7, 12, tzinfo=UTC))
            )

        result = CaptureMediaCleanup(repository, storage).run_once(
            datetime(2026, 7, 13, tzinfo=UTC)
        )

        assert result.claimed == 1
        assert result.deleted == 1
        with repository.engine.connect() as connection:
            capture = (
                connection.execute(
                    select(repository._captures).where(repository._captures.c.id == capture_id)
                )
                .mappings()
                .one()
            )
            audits = (
                connection.execute(
                    select(repository._audits).where(repository._audits.c.resource_id == capture_id)
                )
                .mappings()
                .all()
            )
        assert capture["deletion_status"] == "deleted"
        assert storage.deleted == [capture["object_key"]]
        assert {audit["event_name"] for audit in audits} == {
            "capture_upload_requested",
            "capture_object_deleted",
        }
    finally:
        learning.close()
        repository.close()


def test_postgresql_ocr_failure_uses_seven_day_retention_without_raw_error() -> None:
    storage = FakeObjectStorage()
    client, learning, repository = _client(storage)
    try:
        session_id = _session(client)
        upload_response = client.post(
            f"/households/{HOUSEHOLD_A}/sessions/{session_id}/capture-uploads",
            headers={
                **_headers(client, "child", CHILD_A),
                "Idempotency-Key": f"pg-ocr-failure-upload-{uuid4()}",
            },
            json={
                "media_type": "image/png",
                "byte_size": 1024,
                "content_sha256": sha256(b"synthetic-ocr-failure").hexdigest(),
            },
        )
        assert upload_response.status_code == 201
        capture = upload_response.json()["capture"]
        storage.upload("image/png", 1024)
        confirmation = client.post(
            f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/upload-confirmations",
            headers={
                **_headers(client, "child", CHILD_A),
                "Idempotency-Key": f"pg-ocr-failure-confirm-{uuid4()}",
            },
            json={"expected_capture_version": capture["version"]},
        )
        assert confirmation.status_code == 201
        capture_id = UUID(capture["id"])
        repository.mark_capture_ocr_failed(UUID(HOUSEHOLD_A), capture_id)
        repository.mark_capture_ocr_failed(UUID(HOUSEHOLD_A), capture_id)

        with repository.engine.connect() as connection:
            stored = (
                connection.execute(
                    select(repository._captures).where(repository._captures.c.id == capture_id)
                )
                .mappings()
                .one()
            )
            audits = (
                connection.execute(
                    select(repository._audits).where(repository._audits.c.resource_id == capture_id)
                )
                .mappings()
                .all()
            )
        now = datetime.now(UTC)
        assert stored["retention_class"] == RetentionClass.OCR_FAILURE.value
        assert now + timedelta(days=6) < stored["expires_at"] <= now + timedelta(days=7, seconds=1)
        assert [audit["event_name"] for audit in audits].count("capture_ocr_failed") == 1
        assert all("synthetic-ocr-failure" not in str(audit) for audit in audits)
    finally:
        learning.close()
        repository.close()


def test_postgresql_ocr_queue_is_idempotent_and_recovers_stale_lease() -> None:
    storage = FakeObjectStorage()
    client, learning, repository = _client(storage)
    queue = PostgresOcrJobQueue(lease_seconds=1)
    try:
        session_id = _session(client)
        upload_response = client.post(
            f"/households/{HOUSEHOLD_A}/sessions/{session_id}/capture-uploads",
            headers={
                **_headers(client, "child", CHILD_A),
                "Idempotency-Key": f"pg-ocr-queue-upload-{uuid4()}",
            },
            json={
                "media_type": "image/png",
                "byte_size": 1024,
                "content_sha256": sha256(b"synthetic-ocr-queue").hexdigest(),
            },
        )
        assert upload_response.status_code == 201
        capture = upload_response.json()["capture"]
        storage.upload("image/png", 1024)
        confirmation = client.post(
            f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/upload-confirmations",
            headers={
                **_headers(client, "child", CHILD_A),
                "Idempotency-Key": f"pg-ocr-queue-confirm-{uuid4()}",
            },
            json={"expected_capture_version": capture["version"]},
        )
        assert confirmation.status_code == 201
        capture_id = UUID(capture["id"])

        first, replayed = queue.enqueue(
            UUID(HOUSEHOLD_A), capture_id, UUID(CHILD_A), "pg-ocr-queue-001"
        )
        same, replayed_again = queue.enqueue(
            UUID(HOUSEHOLD_A), capture_id, UUID(CHILD_A), "pg-ocr-queue-001"
        )
        assert replayed is False
        assert replayed_again is True
        assert same == first

        claimed = queue.claim_next()
        assert claimed is not None
        assert claimed.id == first.id
        assert claimed.status is OcrJobStatus.RUNNING
        assert claimed.attempt == 1
        assert queue.claim_next() is None
        queue.fail(claimed.id)
        assert queue.get(claimed.id).error_code == "ocr_job_failed"

        retry, retry_replayed = queue.enqueue(
            UUID(HOUSEHOLD_A), capture_id, UUID(CHILD_A), "pg-ocr-queue-002"
        )
        assert retry_replayed is False
        running_retry = queue.claim_next()
        assert running_retry is not None
        assert running_retry.id == retry.id
        with queue.engine.begin() as connection:
            connection.execute(
                queue._jobs.update()
                .where(queue._jobs.c.id == retry.id)
                .values(started_at=datetime.now(UTC) - timedelta(seconds=10))
            )
        reclaimed = queue.claim_next()
        assert reclaimed is not None
        assert reclaimed.id == retry.id
        assert reclaimed.attempt == 2
        queue.fail(retry.id)

        formula, formula_replayed = queue.enqueue(
            UUID(HOUSEHOLD_A),
            capture_id,
            UUID(CHILD_A),
            "pg-ocr-queue-formula",
            mode=OcrMode.FORMULA,
        )
        assert formula_replayed is False
        assert formula.mode is OcrMode.FORMULA
        with pytest.raises(OcrJobIdempotencyConflictError):
            queue.enqueue(
                UUID(HOUSEHOLD_A),
                capture_id,
                UUID(CHILD_A),
                "pg-ocr-queue-formula",
                mode=OcrMode.TEXT,
            )
        formula_claimed = queue.claim_next()
        assert formula_claimed is not None
        assert formula_claimed.mode is OcrMode.FORMULA
        queue.fail(formula.id)
    finally:
        queue.close()
        learning.close()
        repository.close()


def test_postgresql_child_capture_cascade_is_household_scoped_and_idempotent() -> None:
    storage = FakeObjectStorage()
    client, learning, repository = _client(storage)
    try:
        session_id = _session(client)
        child_id = uuid4()
        capture_id = uuid4()
        capture = Capture(
            id=capture_id,
            household_id=UUID(HOUSEHOLD_A),
            child_id=child_id,
            session_id=UUID(session_id),
            media_type="image/jpeg",
            byte_size=1024,
            content_sha256=sha256(b"synthetic-cascade").hexdigest(),
            status=CaptureStatus.UPLOAD_PENDING,
            version=1,
            created_at=datetime.now(UTC),
        )
        object_key = f"captures/{capture_id}/source"
        with repository.engine.begin() as connection:
            connection.execute(
                repository._captures.insert().values(
                    **capture.model_dump(),
                    object_key=object_key,
                    retention_class="original",
                    expires_at=datetime(2026, 7, 14, tzinfo=UTC),
                    deletion_status=DeletionStatus.ACTIVE.value,
                    parent_saved=False,
                )
            )

        cascade = CaptureObjectCascadeDeletion(
            repository,
            storage,
        )
        first = cascade.run_once(UUID(HOUSEHOLD_A), child_id)
        second = cascade.run_once(UUID(HOUSEHOLD_A), child_id)
        wrong_household = cascade.run_once(UUID("00000000-0000-0000-0000-000000000002"), child_id)

        assert first.claimed == 1
        assert first.deleted == 1
        assert first.failed == 0
        assert second.claimed == 0
        assert wrong_household.claimed == 0
        with repository.engine.connect() as connection:
            capture = (
                connection.execute(
                    select(repository._captures).where(repository._captures.c.id == capture_id)
                )
                .mappings()
                .one()
            )
        assert capture["deletion_status"] == DeletionStatus.DELETED.value
        assert storage.deleted == [object_key]
    finally:
        learning.close()
        repository.close()


def test_postgresql_parent_save_and_delete_media_is_retryable() -> None:
    storage = FakeObjectStorage()
    client, learning, repository = _client(storage)
    try:
        session_id = _session(client)
        upload_response = client.post(
            f"/households/{HOUSEHOLD_A}/sessions/{session_id}/capture-uploads",
            headers={
                **_headers(client, "child", CHILD_A),
                "Idempotency-Key": f"pg-parent-save-upload-{uuid4()}",
            },
            json={
                "media_type": "image/png",
                "byte_size": 1024,
                "content_sha256": sha256(b"synthetic-parent-save").hexdigest(),
            },
        )
        assert upload_response.status_code == 201
        capture = upload_response.json()["capture"]
        storage.upload("image/png", 1024)
        confirmed = client.post(
            f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/upload-confirmations",
            headers={
                **_headers(client, "child", CHILD_A),
                "Idempotency-Key": f"pg-parent-save-confirm-{uuid4()}",
            },
            json={"expected_capture_version": capture["version"]},
        )
        assert confirmed.status_code == 201

        save_headers = {**_headers(client), "Idempotency-Key": "pg-parent-save-001"}
        first_save = client.post(
            f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/save", headers=save_headers
        )
        replay_save = client.post(
            f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/save", headers=save_headers
        )
        delete_headers = {**_headers(client), "Idempotency-Key": "pg-parent-delete-001"}
        first_delete = client.delete(
            f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/media", headers=delete_headers
        )
        replay_delete = client.delete(
            f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/media", headers=delete_headers
        )

        assert first_save.status_code == 204
        assert replay_save.status_code == 204
        assert replay_save.headers["Idempotency-Replayed"] == "true"
        assert first_delete.status_code == 204
        assert replay_delete.status_code == 204
        assert replay_delete.headers["Idempotency-Replayed"] == "true"
        assert storage.deleted == [storage.object_key]
        with repository.engine.connect() as connection:
            stored = (
                connection.execute(
                    select(repository._captures).where(
                        repository._captures.c.id == UUID(capture["id"])
                    )
                )
                .mappings()
                .one()
            )
        assert stored["parent_saved"] is True
        assert stored["deletion_status"] == DeletionStatus.DELETED.value
    finally:
        learning.close()
        repository.close()
