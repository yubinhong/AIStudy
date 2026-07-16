from hashlib import sha256

from fastapi.testclient import TestClient
from test_capture_uploads import (  # noqa: PLC2701 -- reuse synthetic local fixtures.
    CHILD_A,
    HOUSEHOLD_A,
    FakeObjectStorage,
    _begin_upload,
    _principal,
    _session,
)

from study_api.main import create_app


def _receipt(content_sha256: str, *, safe: bool = True) -> dict[str, object]:
    return {
        "schema_version": "privacy-sanitization.v1",
        "sanitizer_version": "privacy-sanitizer.synthetic-v1",
        "safe_to_upload": safe,
        "requires_confirmation": True,
        "sensitive_types": [],
        "region_count": 0,
        "face_detected": False,
        "qr_detected": False,
        "barcode_detected": False,
        "blocked_reasons": [] if safe else ["low_detection_confidence"],
        "sanitized_derivative_sha256": content_sha256,
    }


def _confirmed_capture() -> tuple[TestClient, FakeObjectStorage, dict[str, object]]:
    storage = FakeObjectStorage()
    client = TestClient(create_app(object_storage=storage))
    upload = _begin_upload(client, str(_session(client)["id"]), "image-analysis-upload")
    capture = upload["capture"]
    storage.upload_declared_object("image/jpeg", 1024, capture["content_sha256"])
    confirmed = client.post(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/upload-confirmations",
        headers={
            **_principal(role="child", child_id=CHILD_A),
            "Idempotency-Key": "image-analysis-confirm",
        },
        json={"expected_capture_version": capture["version"]},
    )
    assert confirmed.status_code == 201
    return client, storage, confirmed.json()


def test_image_analysis_records_blocked_job_without_provider_or_image_bytes() -> None:
    client, _, capture = _confirmed_capture()
    payload = {
        "expected_capture_version": capture["version"],
        "sanitization": _receipt(capture["content_sha256"]),
        "user_confirmed": True,
    }
    headers = {
        **_principal(role="child", child_id=CHILD_A),
        "Idempotency-Key": "image-analysis-start",
    }
    first = client.post(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/image-analysis-jobs",
        headers=headers,
        json=payload,
    )
    replay = client.post(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/image-analysis-jobs",
        headers=headers,
        json=payload,
    )

    assert first.status_code == 202
    assert first.json()["status"] == "blocked"
    assert first.json()["error_code"] == "provider_not_enabled"
    assert replay.status_code == 200
    assert replay.headers["Idempotency-Replayed"] == "true"

    job_id = first.json()["id"]
    read = client.get(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/image-analysis-jobs/{job_id}",
        headers=_principal(role="child", child_id=CHILD_A),
    )
    assert read.status_code == 200
    assert read.json()["sanitized_derivative_sha256"] == capture["content_sha256"]


def test_image_analysis_blocks_unsafe_or_mismatched_receipts() -> None:
    client, _, capture = _confirmed_capture()
    unsafe = _receipt(capture["content_sha256"], safe=False)
    unsafe_response = client.post(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/image-analysis-jobs",
        headers={
            **_principal(role="child", child_id=CHILD_A),
            "Idempotency-Key": "image-analysis-unsafe",
        },
        json={
            "expected_capture_version": capture["version"],
            "sanitization": unsafe,
            "user_confirmed": True,
        },
    )
    assert unsafe_response.status_code == 202
    assert unsafe_response.json()["error_code"] == "sanitization_blocked"

    mismatch = _receipt(sha256(b"different-derivative").hexdigest())
    mismatch_response = client.post(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/image-analysis-jobs",
        headers={
            **_principal(role="child", child_id=CHILD_A),
            "Idempotency-Key": "image-analysis-mismatch",
        },
        json={
            "expected_capture_version": capture["version"],
            "sanitization": mismatch,
            "user_confirmed": True,
        },
    )
    assert mismatch_response.status_code == 202
    assert mismatch_response.json()["error_code"] == "sanitization_hash_mismatch"


def test_image_analysis_queues_only_when_newapi_is_explicitly_enabled(monkeypatch) -> None:
    monkeypatch.setenv("STUDY_NEWAPI_ENABLED", "true")
    monkeypatch.setenv("STUDY_NEWAPI_BASE_URL", "http://127.0.0.1:3000")
    monkeypatch.setenv("STUDY_NEWAPI_API_KEY", "local-test-key")
    monkeypatch.setenv("STUDY_NEWAPI_VISION_MODEL", "local-vision")
    client, _, capture = _confirmed_capture()
    response = client.post(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/image-analysis-jobs",
        headers={
            **_principal(role="child", child_id=CHILD_A),
            "Idempotency-Key": "image-analysis-queue",
        },
        json={
            "expected_capture_version": capture["version"],
            "sanitization": _receipt(capture["content_sha256"]),
            "user_confirmed": True,
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert response.json()["error_code"] is None
