from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from auth_helpers import session_headers
from fastapi.testclient import TestClient

from study_api.main import create_app
from study_api.object_storage import ObjectStorageError, PresignedUpload

HOUSEHOLD_A = "00000000-0000-0000-0000-000000000001"
HOUSEHOLD_B = "00000000-0000-0000-0000-000000000002"
CHILD_A = "00000000-0000-0000-0000-000000000101"
CHILD_B = "00000000-0000-0000-0000-000000000102"


class FakeObjectStorage:
    """Synthetic private-object boundary; tests never use a real image or URL."""

    def __init__(self) -> None:
        self.last_object_key: str | None = None
        self._objects: dict[str, tuple[str, int, str]] = {}

    def ensure_bucket(self) -> None:
        return None

    def create_put_url(self, object_key: str, content_type: str, byte_size: int) -> PresignedUpload:
        self.last_object_key = object_key
        return PresignedUpload(
            url="https://synthetic.invalid/private-upload",
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )

    def upload_declared_object(
        self, content_type: str, byte_size: int, content_sha256: str | None = None
    ) -> None:
        assert self.last_object_key is not None
        self._objects[self.last_object_key] = (
            content_type,
            byte_size,
            content_sha256 or sha256(b"synthetic-upload-metadata").hexdigest(),
        )

    def validate_uploaded_object(
        self, object_key: str, content_type: str, byte_size: int, content_sha256: str
    ) -> None:
        if self._objects.get(object_key) != (content_type, byte_size, content_sha256):
            raise ObjectStorageError("synthetic object metadata mismatch")


def _principal(
    client: TestClient,
    household_id: str = HOUSEHOLD_A,
    role: str = "parent",
    child_id: str | None = None,
) -> dict[str, str]:
    return session_headers(client, role=role, household_id=household_id, child_id=child_id)


def _session(client: TestClient) -> dict[str, object]:
    task = client.post(
        f"/households/{HOUSEHOLD_A}/tasks",
        headers={**_principal(client), "Idempotency-Key": f"upload-task-{uuid4()}"},
        json={
            "child_id": CHILD_A,
            "title": "Synthetic upload task",
            "subject": "math",
            "scheduled_for": "2026-07-13",
        },
    ).json()
    response = client.post(
        f"/households/{HOUSEHOLD_A}/tasks/{task['id']}/sessions",
        headers={
            **_principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": f"upload-session-{uuid4()}",
        },
        json={"expected_task_version": task["version"]},
    )
    assert response.status_code == 201
    return response.json()


def _begin_upload(
    client: TestClient, session_id: str, key: str = "capture-upload-001"
) -> dict[str, object]:
    response = client.post(
        f"/households/{HOUSEHOLD_A}/sessions/{session_id}/capture-uploads",
        headers={**_principal(client, role="child", child_id=CHILD_A), "Idempotency-Key": key},
        json={
            "media_type": "image/jpeg",
            "byte_size": 1024,
            "content_sha256": sha256(b"synthetic-upload-metadata").hexdigest(),
        },
    )
    assert response.status_code == 201
    return response.json()


def test_capture_upload_requires_server_verified_private_object_and_is_idempotent() -> None:
    storage = FakeObjectStorage()
    client = TestClient(create_app(object_storage=storage))
    upload = _begin_upload(client, str(_session(client)["id"]))
    capture = upload["capture"]

    assert capture["status"] == "upload_pending"
    assert set(upload) == {"capture", "upload_url", "upload_expires_at"}
    assert "object_key" not in str(upload)

    missing_object = client.post(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/upload-confirmations",
        headers={
            **_principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": "confirm-missing",
        },
        json={"expected_capture_version": capture["version"]},
    )
    assert missing_object.status_code == 409

    storage.upload_declared_object("image/jpeg", 1024)
    headers = {
        **_principal(client, role="child", child_id=CHILD_A),
        "Idempotency-Key": "confirm-upload-001",
    }
    payload = {"expected_capture_version": capture["version"]}
    confirmed = client.post(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/upload-confirmations",
        headers=headers,
        json=payload,
    )
    replay = client.post(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/upload-confirmations",
        headers=headers,
        json=payload,
    )

    assert confirmed.status_code == 201
    assert confirmed.json()["status"] == "needs_correction"
    assert confirmed.json()["version"] == 2
    assert replay.status_code == 200
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.json() == confirmed.json()


def test_capture_upload_child_and_household_boundaries_are_not_enumerable() -> None:
    storage = FakeObjectStorage()
    client = TestClient(create_app(object_storage=storage))
    upload = _begin_upload(client, str(_session(client)["id"]))
    capture_id = upload["capture"]["id"]
    payload = {"expected_capture_version": 1}

    sibling = client.post(
        f"/households/{HOUSEHOLD_A}/captures/{capture_id}/upload-confirmations",
        headers={
            **_principal(client, role="child", child_id=CHILD_B),
            "Idempotency-Key": "confirm-sibling",
        },
        json=payload,
    )
    other_household = client.post(
        f"/households/{HOUSEHOLD_B}/captures/{capture_id}/upload-confirmations",
        headers={
            **_principal(client, HOUSEHOLD_B, "child", CHILD_B),
            "Idempotency-Key": "confirm-household",
        },
        json=payload,
    )

    assert sibling.status_code == 404
    assert other_household.status_code == 404


def test_ocr_job_requires_confirmed_upload_and_is_idempotent() -> None:
    storage = FakeObjectStorage()
    client = TestClient(create_app(object_storage=storage))
    upload = _begin_upload(client, str(_session(client)["id"]), "ocr-upload-001")
    capture = upload["capture"]

    pending = client.post(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/ocr-jobs",
        headers={
            **_principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": "ocr-job-pending",
        },
    )
    assert pending.status_code == 409

    storage.upload_declared_object("image/jpeg", 1024)
    confirmed = client.post(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/upload-confirmations",
        headers={
            **_principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": "ocr-confirm-001",
        },
        json={"expected_capture_version": capture["version"]},
    )
    assert confirmed.status_code == 201

    headers = {
        **_principal(client, role="child", child_id=CHILD_A),
        "Idempotency-Key": "ocr-job-001",
    }
    first = client.post(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/ocr-jobs", headers=headers
    )
    replay = client.post(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/ocr-jobs", headers=headers
    )

    assert first.status_code == 202
    assert first.json()["status"] == "queued"
    assert replay.status_code == 200
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.json() == first.json()

    job_id = first.json()["id"]
    status_response = client.get(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/ocr-jobs/{job_id}",
        headers=_principal(client, role="child", child_id=CHILD_A),
    )
    assert status_response.status_code == 200
    assert status_response.json() == first.json()

    formula = client.post(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/ocr-jobs",
        headers={
            **_principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": "ocr-job-formula",
        },
        json={"mode": "formula"},
    )
    assert formula.status_code == 202
    assert formula.json()["mode"] == "formula"

    conflicting_mode = client.post(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/ocr-jobs",
        headers={
            **_principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": "ocr-job-formula",
        },
        json={"mode": "text"},
    )
    assert conflicting_mode.status_code == 409

    sibling_status = client.get(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/ocr-jobs/{job_id}",
        headers=_principal(client, role="child", child_id=CHILD_B),
    )
    assert sibling_status.status_code == 404
