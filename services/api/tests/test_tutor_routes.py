from uuid import uuid4

from auth_helpers import session_headers
from fastapi.testclient import TestClient

from study_api.main import create_app

HOUSEHOLD_A = "00000000-0000-0000-0000-000000000001"
CHILD_A = "00000000-0000-0000-0000-000000000101"


def _principal(
    client: TestClient, *, role: str = "parent", child_id: str | None = None
) -> dict[str, str]:
    return session_headers(client, role=role, child_id=child_id)


def _corrected_capture(client: TestClient) -> dict[str, object]:
    task = client.post(
        f"/households/{HOUSEHOLD_A}/tasks",
        headers={**_principal(client), "Idempotency-Key": f"tutor-task-{uuid4()}"},
        json={
            "child_id": CHILD_A,
            "title": "Tutor synthetic task",
            "subject": "math",
            "scheduled_for": "2026-07-15",
        },
    ).json()
    session = client.post(
        f"/households/{HOUSEHOLD_A}/tasks/{task['id']}/sessions",
        headers={
            **_principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": f"tutor-session-{uuid4()}",
        },
        json={"expected_task_version": task["version"]},
    ).json()
    capture = client.post(
        f"/households/{HOUSEHOLD_A}/sessions/{session['id']}/captures",
        headers={
            **_principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": f"tutor-capture-{uuid4()}",
        },
        json={
            "media_type": "image/jpeg",
            "byte_size": 100,
            "content_sha256": "a" * 64,
        },
    ).json()
    correction = client.post(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/corrections",
        headers={
            **_principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": f"tutor-correction-{uuid4()}",
        },
        json={"expected_capture_version": capture["version"], "corrected_text": "3/4 + 1/8 = ?"},
    )
    assert correction.status_code == 201
    return correction.json()


def _question(capture_id: str) -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "capture_id": capture_id,
        "extraction_id": str(uuid4()),
        "version": 1,
        "subject": "math",
        "question_text": "3/4 + 1/8 = ?",
        "options": [],
        "formulas": ["3/4 + 1/8"],
        "has_diagram": False,
        "has_handwriting": False,
        "answer_text": "7/8",
        "verified_by": "child",
        "verified_at": "2026-07-15T00:00:00Z",
    }


def test_tutor_hint_requires_corrected_capture_and_returns_no_answer() -> None:
    client = TestClient(create_app())
    correction = _corrected_capture(client)
    payload = {
        "verified_question": _question(correction["capture_id"]),
        "level": 2,
        "child_id": CHILD_A,
    }
    response = client.post(
        f"/households/{HOUSEHOLD_A}/tutor/hints",
        headers={
            **_principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": "tutor-hint-001",
        },
        json=payload,
    )
    assert response.status_code == 200
    assert response.json()["provider"] == "local-policy"
    assert response.json()["direct_answer"] is None
    assert "7/8" not in response.text


def test_tutor_hint_rejects_parent_or_child_mismatch() -> None:
    client = TestClient(create_app())
    correction = _corrected_capture(client)
    payload = {
        "verified_question": _question(correction["capture_id"]),
        "level": 1,
        "child_id": CHILD_A,
    }
    parent = client.post(
        f"/households/{HOUSEHOLD_A}/tutor/hints",
        headers={**_principal(client), "Idempotency-Key": "tutor-hint-parent"},
        json=payload,
    )
    mismatch = client.post(
        f"/households/{HOUSEHOLD_A}/tutor/hints",
        headers={
            **_principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": "tutor-hint-mismatch",
        },
        json={**payload, "child_id": "00000000-0000-0000-0000-000000000102"},
    )
    assert parent.status_code == 403
    assert mismatch.status_code == 404
