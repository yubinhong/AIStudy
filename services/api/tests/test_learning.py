from datetime import date, timedelta
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


def test_parent_can_scope_task_list_to_selected_child() -> None:
    client = TestClient(create_app())
    first = create_task(client)
    sibling_profile = client.post(
        f"/households/{HOUSEHOLD_A}/children",
        headers={**principal(client), "Idempotency-Key": "scope-child-profile"},
        json={
            "display_name": "Scope Child",
            "grade": 3,
            "curriculum_version": "math-demo-2026",
            "subjects": ["math"],
        },
    )
    selected_child_id = sibling_profile.json()["id"]
    second = client.post(
        f"/households/{HOUSEHOLD_A}/tasks",
        headers={**principal(client), "Idempotency-Key": "task-create-child-b"},
        json={
            "child_id": selected_child_id,
            "title": "Sibling fraction practice",
            "subject": "math",
            "scheduled_for": date(2026, 7, 13).isoformat(),
        },
    )

    selected = client.get(
        f"/households/{HOUSEHOLD_A}/tasks?child_id={selected_child_id}",
        headers=principal(client),
    )
    mismatched_child = client.get(
        f"/households/{HOUSEHOLD_A}/tasks?child_id={selected_child_id}",
        headers=principal(client, role="child", child_id=CHILD_A),
    )

    assert sibling_profile.status_code == 201
    assert second.status_code == 201
    assert [item["id"] for item in selected.json()] == [second.json()["id"]]
    assert first["id"] not in {item["id"] for item in selected.json()}
    assert mismatched_child.status_code == 404


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


def test_bound_child_can_resume_only_own_active_task_session() -> None:
    client = TestClient(create_app())
    task = create_task(client)
    session = start_session(client, task)
    path = f"/households/{HOUSEHOLD_A}/tasks/{task['id']}/active-session"

    own = client.get(path, headers=principal(client, role="child", child_id=CHILD_A))
    sibling = client.get(path, headers=principal(client, role="child", child_id=CHILD_B))

    assert own.status_code == 200
    assert own.json() == session
    assert sibling.status_code == 404


def test_task_cannot_start_a_second_active_session() -> None:
    client = TestClient(create_app())
    task = create_task(client)
    first = start_session(client, task)
    current = client.get(
        f"/households/{HOUSEHOLD_A}/tasks",
        headers=principal(client, role="child", child_id=CHILD_A),
    ).json()[0]

    second = client.post(
        f"/households/{HOUSEHOLD_A}/tasks/{task['id']}/sessions",
        headers={
            **principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": "session-start-duplicate",
        },
        json={"expected_task_version": current["version"]},
    )

    assert first["status"] == "active"
    assert second.status_code == 409
    assert second.json() == {
        "code": "HTTP_409",
        "message": "task is no longer available to start",
    }


def test_child_completes_session_with_an_explicit_review_outcome() -> None:
    client = TestClient(create_app())
    task = create_task(client)
    session = start_session(client, task)
    path = f"/households/{HOUSEHOLD_A}/sessions/{session['id']}/completion"
    headers = {
        **principal(client, role="child", child_id=CHILD_A),
        "Idempotency-Key": "session-complete-review",
    }

    first = client.post(path, headers=headers, json={"outcome": "needs_review"})
    replay = client.post(path, headers=headers, json={"outcome": "needs_review"})
    changed = client.post(
        path,
        headers={**headers, "Idempotency-Key": "session-complete-learned"},
        json={"outcome": "learned"},
    )
    tasks = client.get(
        f"/households/{HOUSEHOLD_A}/tasks",
        headers=principal(client, role="child", child_id=CHILD_A),
    )

    assert first.status_code == 200
    assert first.json()["status"] == "completed"
    assert first.json()["outcome"] == "needs_review"
    assert first.json()["completed_at"] is not None
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.json() == first.json()
    assert changed.status_code == 409
    assert tasks.json()[0]["status"] == "completed"


def test_child_can_skip_a_task_and_the_skip_is_idempotent() -> None:
    client = TestClient(create_app())
    task = create_task(client)
    session = start_session(client, task)
    path = f"/households/{HOUSEHOLD_A}/sessions/{session['id']}/completion"
    headers = {
        **principal(client, role="child", child_id=CHILD_A),
        "Idempotency-Key": "session-skip-001",
    }

    first = client.post(path, headers=headers, json={"outcome": "skipped"})
    replay = client.post(path, headers=headers, json={"outcome": "skipped"})
    tasks = client.get(
        f"/households/{HOUSEHOLD_A}/tasks",
        headers=principal(client, role="child", child_id=CHILD_A),
    )

    assert first.status_code == 200
    assert first.json()["status"] == "completed"
    assert first.json()["outcome"] == "skipped"
    assert replay.status_code == 200
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.json() == first.json()
    assert tasks.json()[0]["status"] == "skipped"


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


def test_daily_task_capacity_is_three_and_revocation_frees_one_slot() -> None:
    client = TestClient(create_app())
    scheduled_for = date.today().isoformat()
    for index in range(3):
        response = client.post(
            f"/households/{HOUSEHOLD_A}/tasks",
            headers={**principal(client), "Idempotency-Key": f"capacity-task-{index:03d}"},
            json={
                "child_id": CHILD_A,
                "title": f"Capacity task {index}",
                "subject": "math",
                "scheduled_for": scheduled_for,
            },
        )
        assert response.status_code == 201

    blocked = client.post(
        f"/households/{HOUSEHOLD_A}/tasks",
        headers={**principal(client), "Idempotency-Key": "capacity-task-blocked"},
        json={
            "child_id": CHILD_A,
            "title": "Capacity task 4",
            "subject": "math",
            "scheduled_for": scheduled_for,
        },
    )
    tasks = client.get(
        f"/households/{HOUSEHOLD_A}/tasks",
        headers=principal(client, role="child", child_id=CHILD_A),
    ).json()
    revoked = client.post(
        f"/households/{HOUSEHOLD_A}/tasks/{tasks[0]['id']}/revoke",
        headers={**principal(client), "Idempotency-Key": "capacity-task-revoke"},
    )
    replacement = client.post(
        f"/households/{HOUSEHOLD_A}/tasks",
        headers={**principal(client), "Idempotency-Key": "capacity-task-replacement"},
        json={
            "child_id": CHILD_A,
            "title": "Capacity replacement",
            "subject": "math",
            "scheduled_for": scheduled_for,
        },
    )

    assert blocked.status_code == 409
    assert blocked.json() == {"code": "HTTP_409", "message": "daily task capacity reached"}
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"
    assert replacement.status_code == 201


def test_future_task_cannot_start_before_its_scheduled_date() -> None:
    client = TestClient(create_app())
    response = client.post(
        f"/households/{HOUSEHOLD_A}/tasks",
        headers={**principal(client), "Idempotency-Key": "future-task-create"},
        json={
            "child_id": CHILD_A,
            "title": "Tomorrow task",
            "subject": "math",
            "scheduled_for": (date.today() + timedelta(days=1)).isoformat(),
        },
    )
    task = response.json()
    started = client.post(
        f"/households/{HOUSEHOLD_A}/tasks/{task['id']}/sessions",
        headers={
            **principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": "future-task-start",
        },
        json={"expected_task_version": task["version"]},
    )

    assert response.status_code == 201
    assert started.status_code == 409
    assert started.json() == {"code": "HTTP_409", "message": "task is not scheduled yet"}


def test_server_session_progress_is_monotonic_and_cross_device_readable() -> None:
    client = TestClient(create_app())
    response = client.post(
        f"/households/{HOUSEHOLD_A}/tasks",
        headers={**principal(client), "Idempotency-Key": "progress-task-create"},
        json={
            "child_id": CHILD_A,
            "title": "Two-step task",
            "subject": "math",
            "scheduled_for": date.today().isoformat(),
            "exercises": [
                {"question_text": "1 + 1 = ?", "source_type": "curriculum"},
                {"question_text": "2 + 2 = ?", "source_type": "curriculum"},
            ],
        },
    )
    task = response.json()
    session = start_session(client, task)
    attempt = client.post(
        f"/households/{HOUSEHOLD_A}/sessions/{session['id']}/attempts",
        headers={
            **principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": "progress-attempt-1",
        },
        json={
            "event_id": str(uuid4()),
            "answer_summary": "first exercise confirmed",
            "next_exercise_index": 1,
        },
    )
    resumed = client.get(
        f"/households/{HOUSEHOLD_A}/tasks/{task['id']}/active-session",
        headers=principal(client, role="child", child_id=CHILD_A),
    )
    skipped_ahead = client.post(
        f"/households/{HOUSEHOLD_A}/sessions/{session['id']}/attempts",
        headers={
            **principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": "progress-attempt-jump",
        },
        json={
            "event_id": str(uuid4()),
            "answer_summary": "jump attempt",
            "next_exercise_index": 3,
        },
    )

    assert response.status_code == 201
    assert attempt.status_code == 201
    assert resumed.status_code == 200
    assert resumed.json()["next_exercise_index"] == 1
    assert skipped_ahead.status_code == 409
    assert skipped_ahead.json() == {
        "code": "HTTP_409",
        "message": "task exercise progress conflict",
    }


def test_parent_revoke_closes_active_session_and_blocks_child_writes() -> None:
    client = TestClient(create_app())
    task = create_task(client)
    session = start_session(client, task)
    path = f"/households/{HOUSEHOLD_A}/tasks/{task['id']}/revoke"
    revoked = client.post(
        path,
        headers={**principal(client), "Idempotency-Key": "revoke-task-001"},
    )
    replay = client.post(
        path,
        headers={**principal(client), "Idempotency-Key": "revoke-task-001"},
    )
    active = client.get(
        f"/households/{HOUSEHOLD_A}/tasks/{task['id']}/active-session",
        headers=principal(client, role="child", child_id=CHILD_A),
    )
    attempt = client.post(
        f"/households/{HOUSEHOLD_A}/sessions/{session['id']}/attempts",
        headers={
            **principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": "revoke-attempt-001",
        },
        json={"event_id": str(uuid4()), "answer_summary": "late answer"},
    )

    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"
    assert replay.status_code == 200
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert active.status_code == 404
    assert attempt.status_code == 409
    assert attempt.json() == {"code": "HTTP_409", "message": "study session is no longer active"}


def test_bound_child_creates_idempotent_capture_session_without_parent_task() -> None:
    client = TestClient(create_app())
    headers = {
        **principal(client, role="child", child_id=CHILD_A),
        "Idempotency-Key": "capture-session-2026-07-17",
    }

    first = client.post(f"/households/{HOUSEHOLD_A}/capture-sessions", headers=headers)
    replay = client.post(f"/households/{HOUSEHOLD_A}/capture-sessions", headers=headers)
    visible_tasks = client.get(
        f"/households/{HOUSEHOLD_A}/tasks",
        headers=principal(client, role="child", child_id=CHILD_A),
    )

    assert first.status_code == 201
    assert first.json()["child_id"] == CHILD_A
    assert first.json()["status"] == "active"
    assert replay.status_code == 200
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.json() == first.json()
    assert [task["title"] for task in visible_tasks.json()] == ["即时拍题"]


def test_parent_and_cross_household_child_cannot_create_capture_session() -> None:
    client = TestClient(create_app())
    parent = client.post(
        f"/households/{HOUSEHOLD_A}/capture-sessions",
        headers={**principal(client), "Idempotency-Key": "capture-session-parent"},
    )
    cross_household = client.post(
        f"/households/{HOUSEHOLD_A}/capture-sessions",
        headers={
            **principal(client, HOUSEHOLD_B, "child", CHILD_B),
            "Idempotency-Key": "capture-session-cross-household",
        },
    )

    assert parent.status_code == 403
    assert cross_household.status_code == 404
