from datetime import date
from hashlib import sha256
from uuid import uuid4

from fastapi.testclient import TestClient

from study_api.main import create_app

HOUSEHOLD_A = "00000000-0000-0000-0000-000000000001"
HOUSEHOLD_B = "00000000-0000-0000-0000-000000000002"
CHILD_A = "00000000-0000-0000-0000-000000000101"
CHILD_B = "00000000-0000-0000-0000-000000000102"


def _principal(
    household_id: str = HOUSEHOLD_A, role: str = "parent", child_id: str | None = None
) -> dict[str, str]:
    headers = {"X-Demo-Household-Id": household_id, "X-Demo-Role": role}
    if child_id is not None:
        headers["X-Demo-Child-Id"] = child_id
    return headers


def _session(client: TestClient) -> dict[str, object]:
    task = client.post(
        f"/households/{HOUSEHOLD_A}/tasks",
        headers={**_principal(), "Idempotency-Key": f"capture-task-{uuid4()}"},
        json={
            "child_id": CHILD_A,
            "title": "Synthetic capture task",
            "subject": "math",
            "scheduled_for": date(2026, 7, 13).isoformat(),
        },
    ).json()
    response = client.post(
        f"/households/{HOUSEHOLD_A}/tasks/{task['id']}/sessions",
        headers={
            **_principal(role="child", child_id=CHILD_A),
            "Idempotency-Key": f"capture-session-{uuid4()}",
        },
        json={"expected_task_version": task["version"]},
    )
    assert response.status_code == 201
    return response.json()


def _create_capture(client: TestClient, session_id: str) -> dict[str, object]:
    response = client.post(
        f"/households/{HOUSEHOLD_A}/sessions/{session_id}/captures",
        headers={
            **_principal(role="child", child_id=CHILD_A),
            "Idempotency-Key": "capture-create-001",
        },
        json={
            "media_type": "image/jpeg",
            "byte_size": 1024,
            "content_sha256": sha256(b"synthetic-capture-only").hexdigest(),
        },
    )
    assert response.status_code == 201
    return response.json()


def test_capture_requires_bound_child_and_starts_with_manual_correction() -> None:
    client = TestClient(create_app())
    session = _session(client)

    missing_child = client.post(
        f"/households/{HOUSEHOLD_A}/sessions/{session['id']}/captures",
        headers={**_principal(role="child"), "Idempotency-Key": "capture-missing-child"},
        json={
            "media_type": "image/jpeg",
            "byte_size": 1024,
            "content_sha256": sha256(b"synthetic-capture-only").hexdigest(),
        },
    )
    capture = _create_capture(client, str(session["id"]))

    assert missing_child.status_code == 403
    assert capture["status"] == "needs_correction"
    assert capture["version"] == 1


def test_capture_correction_is_append_only_idempotent_and_versioned() -> None:
    client = TestClient(create_app())
    capture = _create_capture(client, str(_session(client)["id"]))
    headers = {
        **_principal(role="child", child_id=CHILD_A),
        "Idempotency-Key": "capture-correction-001",
    }
    payload = {"expected_capture_version": capture["version"], "corrected_text": "synthetic 3 + 4"}

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
    stale = client.post(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/corrections",
        headers={**headers, "Idempotency-Key": "capture-correction-stale"},
        json={"expected_capture_version": 1, "corrected_text": "synthetic 7"},
    )

    assert first.status_code == 201
    assert first.json()["sequence"] == 1
    assert replay.status_code == 200
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.json() == first.json()
    assert stale.status_code == 409
    assert stale.json() == {"code": "HTTP_409", "message": "capture version conflict"}


def test_capture_cross_household_and_sibling_access_are_not_enumerable() -> None:
    client = TestClient(create_app())
    capture = _create_capture(client, str(_session(client)["id"]))

    sibling = client.post(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/corrections",
        headers={
            **_principal(role="child", child_id=CHILD_B),
            "Idempotency-Key": "capture-sibling-001",
        },
        json={"expected_capture_version": 1, "corrected_text": "synthetic sibling"},
    )
    other_household = client.post(
        f"/households/{HOUSEHOLD_B}/captures/{capture['id']}/corrections",
        headers={
            **_principal(HOUSEHOLD_B, "child", CHILD_B),
            "Idempotency-Key": "capture-household-001",
        },
        json={"expected_capture_version": 1, "corrected_text": "synthetic household"},
    )

    assert sibling.status_code == 404
    assert other_household.status_code == 404


def test_parent_save_and_immediate_delete_are_idempotent_and_child_forbidden() -> None:
    client = TestClient(create_app())
    capture = _create_capture(client, str(_session(client)["id"]))
    save_headers = {**_principal(), "Idempotency-Key": "capture-save-001"}
    first_save = client.post(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/save", headers=save_headers
    )
    replay_save = client.post(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/save", headers=save_headers
    )
    child_save = client.post(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/save",
        headers={
            **_principal(role="child", child_id=CHILD_A),
            "Idempotency-Key": "capture-save-child",
        },
    )
    first_delete = client.delete(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/media",
        headers={**_principal(), "Idempotency-Key": "capture-delete-001"},
    )
    replay_delete = client.delete(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/media",
        headers={**_principal(), "Idempotency-Key": "capture-delete-001"},
    )

    assert first_save.status_code == 204
    assert replay_save.status_code == 204
    assert replay_save.headers["Idempotency-Replayed"] == "true"
    assert child_save.status_code == 403
    assert first_delete.status_code == 204
    assert replay_delete.status_code == 204
    assert replay_delete.headers["Idempotency-Replayed"] == "true"
