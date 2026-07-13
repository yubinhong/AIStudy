from datetime import date
from hashlib import sha256
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from study_api.domain.repository import InMemoryProfileRepository
from study_api.domain.sql_capture_repository import PostgresCaptureRepository
from study_api.domain.sql_learning_repository import PostgresLearningRepository
from study_api.main import create_app

HOUSEHOLD_A = "00000000-0000-0000-0000-000000000001"
CHILD_A = "00000000-0000-0000-0000-000000000101"

pytestmark = pytest.mark.integration


def _headers(role: str = "parent", child_id: str | None = None) -> dict[str, str]:
    headers = {"X-Demo-Household-Id": HOUSEHOLD_A, "X-Demo-Role": role}
    if child_id is not None:
        headers["X-Demo-Child-Id"] = child_id
    return headers


def _client() -> tuple[TestClient, PostgresLearningRepository, PostgresCaptureRepository]:
    profiles = InMemoryProfileRepository()
    learning = PostgresLearningRepository(profiles)
    captures = PostgresCaptureRepository()
    return TestClient(create_app(profiles, learning, captures)), learning, captures


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
