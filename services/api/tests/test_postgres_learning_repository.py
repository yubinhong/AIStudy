from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from auth_helpers import session_headers
from fastapi.testclient import TestClient
from sqlalchemy import select

from study_api.domain.learning_repository import ResourceVersionConflictError
from study_api.domain.models import CreateTaskRequest, StartStudySessionRequest, Subject
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


def _create_task_and_session(client: TestClient) -> tuple[str, int, str]:
    task_key = f"pg-task-{uuid4()}"
    created = client.post(
        f"/households/{HOUSEHOLD_A}/tasks",
        headers={**_principal(client), "Idempotency-Key": task_key},
        json={
            "child_id": CHILD_A,
            "title": "Synthetic PostgreSQL fraction practice",
            "subject": "math",
            "scheduled_for": date(2026, 7, 13).isoformat(),
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
                scheduled_for=date(2026, 7, 13),
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
