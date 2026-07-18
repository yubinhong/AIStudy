from uuid import uuid4

from auth_helpers import session_headers
from fastapi.testclient import TestClient

from study_api.main import create_app

HOUSEHOLD_A = "00000000-0000-0000-0000-000000000001"
CHILD_A = "00000000-0000-0000-0000-000000000101"


def child_headers(client: TestClient) -> dict[str, str]:
    return session_headers(client, role="child", household_id=HOUSEHOLD_A, child_id=CHILD_A)


def test_child_can_create_and_replay_mistake_record() -> None:
    client = TestClient(create_app())
    payload = {
        "verified_question_id": str(uuid4()),
        "session_id": str(uuid4()),
        "reason": "worked_step_error",
    }
    headers = {**child_headers(client), "Idempotency-Key": "mistake-create-001"}
    first = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/mistakes",
        headers=headers,
        json=payload,
    )
    replay = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/mistakes",
        headers=headers,
        json=payload,
    )

    assert first.status_code == 201
    assert first.json()["mistake"]["status"] == "open"
    assert first.json()["schedule"]["interval_days"] == 1
    assert replay.status_code == 200
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.json() == first.json()


def test_review_schedule_is_deterministic_and_due_filter_is_scoped() -> None:
    client = TestClient(create_app())
    mistake = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/mistakes",
        headers={**child_headers(client), "Idempotency-Key": "mistake-create-002"},
        json={
            "verified_question_id": str(uuid4()),
            "session_id": str(uuid4()),
            "reason": "blank_confirmed",
        },
    ).json()
    mistake_id = mistake["mistake"]["id"]
    reviewed = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/mistakes/{mistake_id}/review",
        headers={**child_headers(client), "Idempotency-Key": "mistake-review-001"},
        json={"outcome": "needs_review"},
    )
    due = client.get(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/mistakes?due_only=true",
        headers=child_headers(client),
    )
    other_child = client.get(
        f"/households/{HOUSEHOLD_A}/children/00000000-0000-0000-0000-000000000102/mistakes",
        headers=child_headers(client),
    )

    assert reviewed.status_code == 200
    assert reviewed.json()["schedule"]["interval_days"] == 1
    assert due.status_code == 200
    assert due.json() == []
    assert other_child.status_code == 404


def test_three_correct_reviews_resolve_a_mistake() -> None:
    client = TestClient(create_app())
    headers = child_headers(client)
    created = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/mistakes",
        headers={**headers, "Idempotency-Key": "mistake-create-003"},
        json={
            "verified_question_id": str(uuid4()),
            "session_id": str(uuid4()),
            "reason": "worked_step_error",
        },
    ).json()
    mistake_id = created["mistake"]["id"]
    for index in range(3):
        response = client.post(
            f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/mistakes/{mistake_id}/review",
            headers={**headers, "Idempotency-Key": f"mistake-review-00{index + 2}"},
            json={"outcome": "correct"},
        )
        assert response.status_code == 200

    result = client.get(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/mistakes",
        headers=headers,
    )
    assert result.status_code == 200
    assert result.json() == []
