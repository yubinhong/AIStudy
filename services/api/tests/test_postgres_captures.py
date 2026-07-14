from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from study_api.domain.models import Capture, CaptureStatus
from study_api.domain.repository import InMemoryProfileRepository
from study_api.domain.sql_capture_repository import PostgresCaptureRepository
from study_api.domain.sql_learning_repository import PostgresLearningRepository
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

HOUSEHOLD_A = "00000000-0000-0000-0000-000000000001"
CHILD_A = "00000000-0000-0000-0000-000000000101"

pytestmark = pytest.mark.integration


class FakeObjectStorage:
    def __init__(self) -> None:
        self.object_key: str | None = None
        self.uploaded: tuple[str, int] | None = None
        self.deleted: list[str] = []

    def ensure_bucket(self) -> None:
        return None

    def create_put_url(self, object_key: str, content_type: str, byte_size: int) -> PresignedUpload:
        self.object_key = object_key
        return PresignedUpload(url="https://synthetic.invalid/upload", expires_at=datetime.now(UTC))

    def upload(self, content_type: str, byte_size: int) -> None:
        self.uploaded = (content_type, byte_size)

    def validate_uploaded_object(self, object_key: str, content_type: str, byte_size: int) -> None:
        if object_key != self.object_key or self.uploaded != (content_type, byte_size):
            raise ObjectStorageError("synthetic object is unavailable")

    def delete_object(self, object_key: str) -> None:
        self.deleted.append(object_key)


def _headers(role: str = "parent", child_id: str | None = None) -> dict[str, str]:
    headers = {"X-Demo-Household-Id": HOUSEHOLD_A, "X-Demo-Role": role}
    if child_id is not None:
        headers["X-Demo-Child-Id"] = child_id
    return headers


def _client(
    object_storage: CaptureObjectStorage | None = None,
) -> tuple[TestClient, PostgresLearningRepository, PostgresCaptureRepository]:
    profiles = InMemoryProfileRepository()
    learning = PostgresLearningRepository(profiles)
    captures = PostgresCaptureRepository()
    return TestClient(create_app(profiles, learning, captures, object_storage)), learning, captures


def _session(client: TestClient) -> str:
    task = client.post(
        f"/households/{HOUSEHOLD_A}/tasks",
        headers={**_headers(), "Idempotency-Key": f"pg-capture-task-{uuid4()}"},
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
            **_headers("child", CHILD_A),
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
                **_headers("child", CHILD_A),
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
            **_headers("child", CHILD_A),
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


def test_postgresql_capture_upload_keeps_object_key_internal_and_confirms_once() -> None:
    storage = FakeObjectStorage()
    client, learning, repository = _client(storage)
    try:
        session_id = _session(client)
        upload_response = client.post(
            f"/households/{HOUSEHOLD_A}/sessions/{session_id}/capture-uploads",
            headers={
                **_headers("child", CHILD_A),
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
                **_headers("child", CHILD_A),
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
    content = b"\xff\xd8\xff\xe0synthetic-api-capture-only\xff\xd9"
    try:
        session_id = _session(client)
        upload_response = client.post(
            f"/households/{HOUSEHOLD_A}/sessions/{session_id}/capture-uploads",
            headers={
                **_headers("child", CHILD_A),
                "Idempotency-Key": f"pg-minio-capture-upload-{uuid4()}",
            },
            json={
                "media_type": "image/jpeg",
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
            headers={"Content-Type": "image/jpeg"},
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
                **_headers("child", CHILD_A),
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


def test_postgresql_capture_cleanup_claims_expired_object_and_records_audit() -> None:
    storage = FakeObjectStorage()
    client, learning, repository = _client(storage)
    try:
        session_id = _session(client)
        upload_response = client.post(
            f"/households/{HOUSEHOLD_A}/sessions/{session_id}/capture-uploads",
            headers={
                **_headers("child", CHILD_A),
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
                **_headers("child", CHILD_A),
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
                **_headers("child", CHILD_A),
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
                **_headers("child", CHILD_A),
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
                **_headers("child", CHILD_A),
                "Idempotency-Key": f"pg-parent-save-confirm-{uuid4()}",
            },
            json={"expected_capture_version": capture["version"]},
        )
        assert confirmed.status_code == 201

        save_headers = {**_headers(), "Idempotency-Key": "pg-parent-save-001"}
        first_save = client.post(
            f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/save", headers=save_headers
        )
        replay_save = client.post(
            f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/save", headers=save_headers
        )
        delete_headers = {**_headers(), "Idempotency-Key": "pg-parent-delete-001"}
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
