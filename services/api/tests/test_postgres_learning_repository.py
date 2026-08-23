from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from auth_helpers import session_headers
from fastapi.testclient import TestClient
from sqlalchemy import select

from study_api.domain.insights_repository import PostgresInsightsRepository
from study_api.domain.learning_repository import (
    ResourceVersionConflictError,
    TaskNotStartableError,
)
from study_api.domain.models import (
    CreateTaskRequest,
    SessionOutcome,
    StartStudySessionRequest,
    Subject,
)
from study_api.domain.repository import InMemoryProfileRepository
from study_api.domain.sql_learning_repository import PostgresLearningRepository
from study_api.main import create_app

HOUSEHOLD_A = "00000000-0000-0000-0000-000000000001"
CHILD_A = "00000000-0000-0000-0000-000000000101"

pytestmark = pytest.mark.integration


def _principal(
    client: TestClient, role: str = "parent", child_id: str | None = None
) -> dict[str, str]:
    return session_headers(client, role=role, child_id=child_id)


def _create_client() -> tuple[TestClient, PostgresLearningRepository]:
    profiles = InMemoryProfileRepository()
    repository = PostgresLearningRepository(profiles)
    return TestClient(create_app(profiles, repository)), repository


def _past_date() -> date:
    return date(2020, 1, 1) + timedelta(days=uuid4().int % 2000)


def _create_task_and_session(
    client: TestClient, scheduled_for: date | None = None
) -> tuple[str, int, str]:
    task_key = f"pg-task-{uuid4()}"
    created = client.post(
        f"/households/{HOUSEHOLD_A}/tasks",
        headers={**_principal(client), "Idempotency-Key": task_key},
        json={
            "child_id": CHILD_A,
            "title": "Synthetic PostgreSQL fraction practice",
            "subject": "math",
            "scheduled_for": (scheduled_for or _past_date()).isoformat(),
        },
    )
    assert created.status_code == 201
    task = created.json()
    started = client.post(
        f"/households/{HOUSEHOLD_A}/tasks/{task['id']}/sessions",
        headers={
            **_principal(client, "child", CHILD_A),
            "Idempotency-Key": f"pg-session-{uuid4()}",
        },
        json={"expected_task_version": task["version"]},
    )
    assert started.status_code == 201
    return task["id"], task["version"], started.json()["id"]


def test_postgresql_repository_persists_append_only_attempts_and_reconnects_pool() -> None:
    client, repository = _create_client()
    try:
        _, _, session_id = _create_task_and_session(client)
        event_id = str(uuid4())
        headers = {
            **_principal(client, "child", CHILD_A),
            "Idempotency-Key": f"pg-attempt-{uuid4()}",
        }
        payload = {"event_id": event_id, "answer_summary": "synthetic persisted answer"}

        created = client.post(
            f"/households/{HOUSEHOLD_A}/sessions/{session_id}/attempts",
            headers=headers,
            json=payload,
        )
        repository.engine.dispose()
        replayed = client.post(
            f"/households/{HOUSEHOLD_A}/sessions/{session_id}/attempts",
            headers=headers,
            json=payload,
        )

        assert created.status_code == 201
        assert replayed.status_code == 200
        assert replayed.headers["Idempotency-Replayed"] == "true"
        assert replayed.json() == created.json()
        with repository.engine.connect() as connection:
            attempts = (
                connection.execute(
                    select(repository._attempts).where(
                        repository._attempts.c.event_id == UUID(event_id)
                    )
                )
                .mappings()
                .all()
            )
            audits = (
                connection.execute(
                    select(repository._audits).where(
                        repository._audits.c.resource_id == UUID(created.json()["id"])
                    )
                )
                .mappings()
                .all()
            )
        assert len(attempts) == 1
        assert attempts[0]["sequence"] == 1
        assert [audit["event_name"] for audit in audits] == ["attempt_recorded"]
    finally:
        repository.close()


def test_postgresql_completion_projects_into_weekly_review_report() -> None:
    client, repository = _create_client()
    insights = PostgresInsightsRepository()
    try:
        report_date = _past_date()
        _, _, session_id = _create_task_and_session(client, report_date)
        response = client.post(
            f"/households/{HOUSEHOLD_A}/sessions/{session_id}/completion",
            headers={
                **_principal(client, "child", CHILD_A),
                "Idempotency-Key": f"pg-complete-{uuid4()}",
            },
            json={"outcome": "needs_review"},
        )
        report = insights.weekly_report(UUID(HOUSEHOLD_A), UUID(CHILD_A), report_date)

        assert response.status_code == 200
        assert response.json()["outcome"] == SessionOutcome.NEEDS_REVIEW.value
        assert report.tasks_completed >= 1
        assert report.sessions_completed >= 1
        assert any(str(item.session_id) == session_id for item in report.review_items)
    finally:
        insights.close()
        repository.close()


def test_postgresql_task_version_rejects_one_of_two_concurrent_session_starts() -> None:
    profiles = InMemoryProfileRepository()
    first_repository = PostgresLearningRepository(profiles)
    second_repository = PostgresLearningRepository(profiles)
    try:
        household_id = UUID(HOUSEHOLD_A)
        child_id = UUID(CHILD_A)
        task, _ = first_repository.create_task(
            household_id,
            CreateTaskRequest(
                child_id=child_id,
                title="Synthetic concurrent session task",
                subject=Subject.MATH,
                scheduled_for=_past_date(),
            ),
            f"pg-concurrent-task-{uuid4()}",
        )
        barrier = Barrier(2)

        def start(repository: PostgresLearningRepository) -> str:
            barrier.wait()
            try:
                repository.start_session(
                    household_id,
                    task.id,
                    child_id,
                    StartStudySessionRequest(expected_task_version=task.version),
                    f"pg-concurrent-session-{uuid4()}",
                )
            except ResourceVersionConflictError:
                return "conflict"
            return "created"

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(start, [first_repository, second_repository]))

        assert sorted(outcomes) == ["conflict", "created"]
        with first_repository.engine.connect() as connection:
            stored_task = (
                connection.execute(
                    select(first_repository._tasks).where(first_repository._tasks.c.id == task.id)
                )
                .mappings()
                .one()
            )
            sessions = (
                connection.execute(
                    select(first_repository._sessions).where(
                        first_repository._sessions.c.task_id == task.id
                    )
                )
                .mappings()
                .all()
            )
        assert stored_task["version"] == 2
        assert len(sessions) == 1
    finally:
        first_repository.close()
        second_repository.close()


def test_postgresql_task_rejects_a_second_active_session_even_at_current_version() -> None:
    profiles = InMemoryProfileRepository()
    repository = PostgresLearningRepository(profiles)
    try:
        household_id = UUID(HOUSEHOLD_A)
        child_id = UUID(CHILD_A)
        task, _ = repository.create_task(
            household_id,
            CreateTaskRequest(
                child_id=child_id,
                title="Synthetic duplicate-session task",
                subject=Subject.MATH,
                scheduled_for=_past_date(),
            ),
            f"pg-duplicate-task-{uuid4()}",
        )
        first, _ = repository.start_session(
            household_id,
            task.id,
            child_id,
            StartStudySessionRequest(expected_task_version=task.version),
            f"pg-duplicate-first-{uuid4()}",
        )

        with pytest.raises(TaskNotStartableError):
            repository.start_session(
                household_id,
                task.id,
                child_id,
                StartStudySessionRequest(expected_task_version=first.task_version),
                f"pg-duplicate-second-{uuid4()}",
            )
    finally:
        repository.close()


def test_postgresql_sync_preflight_rejects_conflicting_batch_without_writes() -> None:
    client, repository = _create_client()
    try:
        _, _, session_id = _create_task_and_session(client)
        duplicated_event_id = str(uuid4())
        valid_event_id = str(uuid4())
        response = client.post(
            f"/households/{HOUSEHOLD_A}/sync-batches",
            headers={
                **_principal(client, "child", CHILD_A),
                "Idempotency-Key": f"pg-batch-{uuid4()}",
            },
            json={
                "schema_version": 1,
                "events": [
                    {
                        "event_id": valid_event_id,
                        "idempotency_key": f"pg-offline-{uuid4()}",
                        "kind": "record_attempt",
                        "session_id": session_id,
                        "answer_summary": "synthetic valid event",
                    },
                    {
                        "event_id": duplicated_event_id,
                        "idempotency_key": f"pg-offline-{uuid4()}",
                        "kind": "record_attempt",
                        "session_id": session_id,
                        "answer_summary": "synthetic duplicate first",
                    },
                    {
                        "event_id": duplicated_event_id,
                        "idempotency_key": f"pg-offline-{uuid4()}",
                        "kind": "record_attempt",
                        "session_id": session_id,
                        "answer_summary": "synthetic duplicate second",
                    },
                ],
            },
        )

        assert response.status_code == 409
        with repository.engine.connect() as connection:
            attempts = (
                connection.execute(
                    select(repository._attempts).where(
                        repository._attempts.c.event_id.in_(
                            [UUID(valid_event_id), UUID(duplicated_event_id)]
                        )
                    )
                )
                .mappings()
                .all()
            )
        assert attempts == []
    finally:
        repository.close()


def test_postgresql_session_progress_survives_a_fresh_repository() -> None:
    client, repository = _create_client()
    try:
        created = client.post(
            f"/households/{HOUSEHOLD_A}/tasks",
            headers={**_principal(client), "Idempotency-Key": f"pg-progress-task-{uuid4()}"},
            json={
                "child_id": CHILD_A,
                "title": "Synthetic resumable task",
                "subject": "math",
                "scheduled_for": _past_date().isoformat(),
                "exercises": [
                    {"question_text": "1 + 1 = ?", "source_type": "curriculum"},
                    {"question_text": "2 + 2 = ?", "source_type": "curriculum"},
                ],
            },
        )
        task = created.json()
        started = client.post(
            f"/households/{HOUSEHOLD_A}/tasks/{task['id']}/sessions",
            headers={
                **_principal(client, "child", CHILD_A),
                "Idempotency-Key": f"pg-progress-session-{uuid4()}",
            },
            json={"expected_task_version": task["version"]},
        )
        session_id = started.json()["id"]
        attempt = client.post(
            f"/households/{HOUSEHOLD_A}/sessions/{session_id}/attempts",
            headers={
                **_principal(client, "child", CHILD_A),
                "Idempotency-Key": f"pg-progress-attempt-{uuid4()}",
            },
            json={
                "event_id": str(uuid4()),
                "answer_summary": "first exercise confirmed",
                "next_exercise_index": 1,
            },
        )
        repository.engine.dispose()
        resumed = client.get(
            f"/households/{HOUSEHOLD_A}/tasks/{task['id']}/active-session",
            headers=_principal(client, "child", CHILD_A),
        )

        assert created.status_code == 201
        assert started.status_code == 201
        assert attempt.status_code == 201
        assert resumed.status_code == 200
        assert resumed.json()["next_exercise_index"] == 1
    finally:
        repository.close()


def test_postgresql_parent_revoke_closes_session_and_releases_capacity() -> None:
    client, repository = _create_client()
    try:
        scheduled_for = _past_date()
        task_ids: list[str] = []
        for index in range(3):
            response = client.post(
                f"/households/{HOUSEHOLD_A}/tasks",
                headers={
                    **_principal(client),
                    "Idempotency-Key": f"pg-capacity-task-{uuid4()}",
                },
                json={
                    "child_id": CHILD_A,
                    "title": f"Synthetic capacity task {index}",
                    "subject": "math",
                    "scheduled_for": scheduled_for.isoformat(),
                },
            )
            assert response.status_code == 201
            task_ids.append(response.json()["id"])
        blocked = client.post(
            f"/households/{HOUSEHOLD_A}/tasks",
            headers={**_principal(client), "Idempotency-Key": f"pg-capacity-blocked-{uuid4()}"},
            json={
                "child_id": CHILD_A,
                "title": "Synthetic blocked capacity task",
                "subject": "math",
                "scheduled_for": scheduled_for.isoformat(),
            },
        )
        revoked = client.post(
            f"/households/{HOUSEHOLD_A}/tasks/{task_ids[0]}/revoke",
            headers={**_principal(client), "Idempotency-Key": f"pg-revoke-{uuid4()}"},
        )
        replacement = client.post(
            f"/households/{HOUSEHOLD_A}/tasks",
            headers={**_principal(client), "Idempotency-Key": f"pg-capacity-replacement-{uuid4()}"},
            json={
                "child_id": CHILD_A,
                "title": "Synthetic replacement task",
                "subject": "math",
                "scheduled_for": scheduled_for.isoformat(),
            },
        )

        assert blocked.status_code == 409
        assert revoked.status_code == 200
        assert revoked.json()["status"] == "revoked"
        assert replacement.status_code == 201
    finally:
        repository.close()


def test_postgresql_capture_session_is_atomic_and_idempotent() -> None:
    client, repository = _create_client()
    try:
        key = f"pg-capture-session-{uuid4()}"
        headers = {**_principal(client, "child", CHILD_A), "Idempotency-Key": key}

        first = client.post(f"/households/{HOUSEHOLD_A}/capture-sessions", headers=headers)
        repository.engine.dispose()
        replay = client.post(f"/households/{HOUSEHOLD_A}/capture-sessions", headers=headers)

        assert first.status_code == 201
        assert replay.status_code == 200
        assert replay.json() == first.json()
        session_id = UUID(first.json()["id"])
        task_id = UUID(first.json()["task_id"])
        with repository.engine.connect() as connection:
            assert connection.execute(
                select(repository._sessions).where(repository._sessions.c.id == session_id)
            ).mappings().one()["child_id"] == UUID(CHILD_A)
            assert (
                connection.execute(
                    select(repository._tasks).where(repository._tasks.c.id == task_id)
                )
                .mappings()
                .one()["title"]
                == "即时拍题"
            )
    finally:
        repository.close()
