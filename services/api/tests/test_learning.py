from datetime import date
from uuid import uuid4

from auth_helpers import session_headers
from fastapi.testclient import TestClient

from study_api.main import create_app

HOUSEHOLD_A = "00000000-0000-0000-0000-000000000001"
HOUSEHOLD_B = "00000000-0000-0000-0000-000000000002"
CHILD_A = "00000000-0000-0000-0000-000000000101"
CHILD_B = "00000000-0000-0000-0000-000000000102"


def principal(
    client: TestClient,
    household_id: str = HOUSEHOLD_A,
    role: str = "parent",
    child_id: str | None = None,
) -> dict[str, str]:
    return session_headers(client, role=role, household_id=household_id, child_id=child_id)


def create_task(client: TestClient) -> dict[str, object]:
    response = client.post(
        f"/households/{HOUSEHOLD_A}/tasks",
        headers={**principal(client), "Idempotency-Key": "task-create-001"},
        json={
            "child_id": CHILD_A,
            "title": "Synthetic fraction practice",
            "subject": "math",
            "scheduled_for": date(2026, 7, 13).isoformat(),
        },
    )
    assert response.status_code == 201
    return response.json()


def start_session(client: TestClient, task: dict[str, object]) -> dict[str, object]:
    response = client.post(
        f"/households/{HOUSEHOLD_A}/tasks/{task['id']}/sessions",
        headers={
            **principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": "session-start-001",
        },
        json={"expected_task_version": task["version"]},
    )
    assert response.status_code == 201
    return response.json()


def test_parent_creates_task_and_bound_child_sees_only_assigned_tasks() -> None:
    client = TestClient(create_app())
    task = create_task(client)

    visible = client.get(
        f"/households/{HOUSEHOLD_A}/tasks",
        headers=principal(client, role="child", child_id=CHILD_A),
    )

    assert visible.status_code == 200
    assert [item["id"] for item in visible.json()] == [task["id"]]


def test_child_cannot_start_session_for_another_household_or_child() -> None:
    client = TestClient(create_app())
    task = create_task(client)

    sibling = client.post(
        f"/households/{HOUSEHOLD_A}/tasks/{task['id']}/sessions",
        headers={
            **principal(client, role="child", child_id=CHILD_B),
            "Idempotency-Key": "session-start-other-child",
        },
        json={"expected_task_version": task["version"]},
    )
    cross_household = client.post(
        f"/households/{HOUSEHOLD_B}/tasks/{task['id']}/sessions",
        headers={
            **principal(client, HOUSEHOLD_B, "child", CHILD_B),
            "Idempotency-Key": "session-start-other-household",
        },
        json={"expected_task_version": task["version"]},
    )

    assert sibling.status_code == 404
    assert cross_household.status_code == 404


def test_session_and_attempt_writes_are_idempotent_and_append_only() -> None:
    client = TestClient(create_app())
    task = create_task(client)
    session = start_session(client, task)
    event_id = str(uuid4())
    headers = {
        **principal(client, role="child", child_id=CHILD_A),
        "Idempotency-Key": "attempt-record-001",
    }
    payload = {"event_id": event_id, "answer_summary": "synthetic answer 1/2"}

    first = client.post(
        f"/households/{HOUSEHOLD_A}/sessions/{session['id']}/attempts",
        headers=headers,
        json=payload,
    )
    replay = client.post(
        f"/households/{HOUSEHOLD_A}/sessions/{session['id']}/attempts",
        headers=headers,
        json=payload,
    )
    conflict = client.post(
        f"/households/{HOUSEHOLD_A}/sessions/{session['id']}/attempts",
        headers=headers,
        json={**payload, "answer_summary": "synthetic changed answer"},
    )

    assert first.status_code == 201
    assert first.json()["sequence"] == 1
    assert replay.status_code == 200
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.json() == first.json()
    assert conflict.status_code == 409


def test_offline_batch_replays_events_and_rejects_conflicts_without_partial_write() -> None:
    client = TestClient(create_app())
    task = create_task(client)
    session = start_session(client, task)
    event_id = str(uuid4())
    headers = {
        **principal(client, role="child", child_id=CHILD_A),
        "Idempotency-Key": "sync-batch-001",
    }
    payload = {
        "schema_version": 1,
        "events": [
            {
                "event_id": event_id,
                "idempotency_key": "offline-attempt-001",
                "kind": "record_attempt",
                "session_id": session["id"],
                "answer_summary": "synthetic offline answer",
            }
        ],
    }

    first = client.post(f"/households/{HOUSEHOLD_A}/sync-batches", headers=headers, json=payload)
    replay = client.post(f"/households/{HOUSEHOLD_A}/sync-batches", headers=headers, json=payload)
    conflict = client.post(
        f"/households/{HOUSEHOLD_A}/sync-batches",
        headers=headers,
        json={
            "schema_version": 1,
            "events": [
                {
                    "event_id": event_id,
                    "idempotency_key": "offline-attempt-001",
                    "kind": "record_attempt",
                    "session_id": session["id"],
                    "answer_summary": "changed offline answer",
                }
            ],
        },
    )

    assert first.status_code == 200
    assert first.json()["results"][0]["status"] == "applied"
    assert replay.status_code == 200
    assert replay.json()["results"][0]["status"] == "replayed"
    assert conflict.status_code == 409


def test_outdated_task_version_is_an_explicit_conflict() -> None:
    client = TestClient(create_app())
    task = create_task(client)
    _ = start_session(client, task)

    stale = client.post(
        f"/households/{HOUSEHOLD_A}/tasks/{task['id']}/sessions",
        headers={
            **principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": "session-start-stale",
        },
        json={"expected_task_version": task["version"]},
    )

    assert stale.status_code == 409
    assert stale.json() == {"code": "HTTP_409", "message": "task version conflict"}
