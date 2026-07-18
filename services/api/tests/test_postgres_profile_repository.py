from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import MetaData, Table, delete, insert, select

from study_api.domain.insights_repository import PostgresInsightsRepository
from study_api.domain.models import (
    CreateChildRequest,
    CreateDeviceRequest,
    CreateTaskRequest,
    DeviceKind,
    DevicePlatform,
    RecordAttemptRequest,
    StartStudySessionRequest,
    Subject,
    UpdateChildRequest,
)
from study_api.domain.repository import IdempotencyConflictError
from study_api.domain.sql_learning_repository import PostgresLearningRepository
from study_api.domain.sql_profile_repository import PostgresProfileRepository

pytestmark = pytest.mark.integration

HOUSEHOLD_A = UUID("00000000-0000-0000-0000-000000000001")
HOUSEHOLD_B = UUID("00000000-0000-0000-0000-000000000002")


def child_request(name: str = "Synthetic persisted child") -> CreateChildRequest:
    return CreateChildRequest(
        display_name=name,
        grade=2,
        curriculum_version="math-demo-2026",
        subjects=[Subject.MATH],
    )


def cleanup(repository: PostgresProfileRepository, resource_ids: set[UUID]) -> None:
    with repository.engine.begin() as connection:
        export_ids = set(
            connection.scalars(
                select(repository._data_exports.c.id).where(
                    repository._data_exports.c.child_id.in_(resource_ids)
                )
            )
        )
        connection.execute(
            delete(repository._idempotency).where(
                repository._idempotency.c.resource_id.in_(resource_ids | export_ids)
            )
        )
        connection.execute(
            delete(repository._audits).where(repository._audits.c.resource_id.in_(resource_ids))
        )
        connection.execute(
            delete(repository._devices).where(repository._devices.c.id.in_(resource_ids))
        )
        connection.execute(
            delete(repository._children).where(repository._children.c.id.in_(resource_ids))
        )


def test_profile_create_update_and_device_survive_repository_reconnect() -> None:
    first = PostgresProfileRepository()
    resource_ids: set[UUID] = set()
    try:
        child_key = f"pg-profile-create-{uuid4()}"
        child, replayed = first.create_child(HOUSEHOLD_A, child_request(), child_key)
        resource_ids.add(child.id)
        assert replayed is False
        replay, replayed = first.create_child(HOUSEHOLD_A, child_request(), child_key)
        assert replayed is True
        assert replay == child

        update = UpdateChildRequest(
            display_name="Synthetic updated child",
            grade=4,
            curriculum_version="math-demo-2026-v2",
            subjects=[Subject.MATH],
        )
        update_key = f"pg-profile-update-{uuid4()}"
        changed, replayed = first.update_child(HOUSEHOLD_A, child.id, update, update_key)
        assert replayed is False
        assert changed is not None and changed.grade == 4

        device, replayed = first.create_device(
            HOUSEHOLD_A,
            CreateDeviceRequest(
                kind=DeviceKind.CHILD,
                platform=DevicePlatform.ANDROID,
                display_name="Synthetic Huawei device",
            ),
            f"pg-device-{uuid4()}",
        )
        resource_ids.add(device.id)
        assert replayed is False
        first.engine.dispose()

        second = PostgresProfileRepository()
        try:
            persisted = second.get_child(HOUSEHOLD_A, child.id)
            assert persisted is not None
            assert persisted.display_name == "Synthetic updated child"
            assert persisted.grade == 4
            assert second.get_child(HOUSEHOLD_B, child.id) is None
            assert [
                item.id for item in second.list_devices(HOUSEHOLD_A) if item.id == device.id
            ] == [device.id]
            replay, replayed = second.update_child(HOUSEHOLD_A, child.id, update, update_key)
            assert replayed is True
            assert replay == persisted
            with pytest.raises(IdempotencyConflictError):
                second.update_child(
                    HOUSEHOLD_A,
                    child.id,
                    update.model_copy(update={"grade": 5}),
                    update_key,
                )
        finally:
            cleanup(second, resource_ids)
            second.close()
    finally:
        first.close()


def test_child_data_export_replay_returns_immutable_short_lived_snapshot() -> None:
    profiles = PostgresProfileRepository()
    insights = PostgresInsightsRepository()
    child, _ = profiles.create_child(HOUSEHOLD_A, child_request(), f"pg-export-child-{uuid4()}")
    key = f"pg-export-{uuid4()}"
    try:
        first, replayed = insights.export_child(HOUSEHOLD_A, child.id, key)
        assert replayed is False
        assert first.child.display_name == "Synthetic persisted child"

        profiles.update_child(
            HOUSEHOLD_A,
            child.id,
            UpdateChildRequest(
                display_name="Changed after export",
                grade=3,
                curriculum_version="math-demo-2026",
                subjects=[Subject.MATH],
            ),
            f"pg-export-update-{uuid4()}",
        )
        replay, replayed = insights.export_child(HOUSEHOLD_A, child.id, key)
        assert replayed is True
        assert replay == first

        with profiles.engine.connect() as connection:
            snapshot = (
                connection.execute(
                    select(profiles._data_exports).where(
                        profiles._data_exports.c.child_id == child.id
                    )
                )
                .mappings()
                .one()
            )
            assert snapshot["expires_at"] == snapshot["created_at"] + timedelta(hours=24)
            export_id = snapshot["id"]
        assert insights.cleanup_expired_exports(snapshot["expires_at"] + timedelta(seconds=1)) == 1
        with profiles.engine.connect() as connection:
            assert (
                connection.execute(
                    select(profiles._idempotency.c.resource_id).where(
                        profiles._idempotency.c.resource_id == export_id
                    )
                ).all()
                == []
            )
    finally:
        cleanup(profiles, {child.id})
        insights.close()
        profiles.close()


def test_concurrent_profile_create_reserves_one_durable_idempotency_result() -> None:
    first = PostgresProfileRepository()
    second = PostgresProfileRepository()
    barrier = Barrier(2)
    key = f"pg-profile-concurrent-{uuid4()}"
    resource_ids: set[UUID] = set()

    def create(repository: PostgresProfileRepository) -> tuple[UUID, bool]:
        barrier.wait()
        child, replayed = repository.create_child(HOUSEHOLD_A, child_request(), key)
        return child.id, replayed

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(create, [first, second]))
        resource_ids = {child_id for child_id, _ in results}
        assert len(resource_ids) == 1
        assert sorted(replayed for _, replayed in results) == [False, True]
        with first.engine.connect() as connection:
            stored = connection.execute(
                select(first._children.c.id).where(first._children.c.id.in_(resource_ids))
            ).all()
        assert len(stored) == 1
    finally:
        cleanup(first, resource_ids)
        first.close()
        second.close()


def test_profile_delete_cascades_bound_child_account_and_session_and_replays() -> None:
    repository = PostgresProfileRepository()
    learning = PostgresLearningRepository(repository)
    metadata = MetaData()
    accounts = Table("accounts", metadata, autoload_with=repository.engine)
    sessions = Table("auth_sessions", metadata, autoload_with=repository.engine)
    child, _ = repository.create_child(
        HOUSEHOLD_A, child_request(), f"pg-profile-delete-create-{uuid4()}"
    )
    account_id = uuid4()
    session_id = uuid4()
    now = datetime.now(UTC)
    delete_key = f"pg-profile-delete-{uuid4()}"
    try:
        with repository.engine.begin() as connection:
            connection.execute(
                insert(accounts).values(
                    id=account_id,
                    household_id=HOUSEHOLD_A,
                    username=f"synthetic-{uuid4()}",
                    role="child",
                    child_id=child.id,
                    password_hash="synthetic-not-a-real-password-hash",
                    must_change_password=False,
                    status="active",
                    failed_login_count=0,
                    locked_until=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            connection.execute(
                insert(sessions).values(
                    id=session_id,
                    account_id=account_id,
                    household_id=HOUSEHOLD_A,
                    token_digest=uuid4().hex + uuid4().hex,
                    created_at=now,
                    expires_at=now + timedelta(hours=1),
                    revoked_at=None,
                )
            )

        task, _ = learning.create_task(
            HOUSEHOLD_A,
            CreateTaskRequest(
                child_id=child.id,
                title="Synthetic child deletion task",
                subject=Subject.MATH,
                scheduled_for=now.date(),
            ),
            f"pg-profile-delete-task-{uuid4()}",
        )
        study_session, _ = learning.start_session(
            HOUSEHOLD_A,
            task.id,
            child.id,
            StartStudySessionRequest(expected_task_version=task.version),
            f"pg-profile-delete-study-session-{uuid4()}",
        )
        attempt, _ = learning.record_attempt(
            HOUSEHOLD_A,
            study_session.id,
            child.id,
            RecordAttemptRequest(event_id=uuid4(), answer_summary="synthetic deletion attempt"),
            f"pg-profile-delete-attempt-{uuid4()}",
        )
        assert repository.delete_child(HOUSEHOLD_A, child.id, delete_key) == (True, False)
        assert repository.delete_child(HOUSEHOLD_A, child.id, delete_key) == (True, True)
        assert repository.get_child(HOUSEHOLD_A, child.id) is None
        with repository.engine.connect() as connection:
            assert (
                connection.execute(select(accounts.c.id).where(accounts.c.id == account_id)).all()
                == []
            )
            assert (
                connection.execute(select(sessions.c.id).where(sessions.c.id == session_id)).all()
                == []
            )
            assert (
                connection.execute(
                    select(learning._tasks.c.id).where(learning._tasks.c.id == task.id)
                ).all()
                == []
            )
            assert (
                connection.execute(
                    select(learning._sessions.c.id).where(
                        learning._sessions.c.id == study_session.id
                    )
                ).all()
                == []
            )
            assert (
                connection.execute(
                    select(learning._attempts.c.id).where(learning._attempts.c.id == attempt.id)
                ).all()
                == []
            )
    finally:
        cleanup(repository, {child.id, account_id, session_id})
        learning.close()
        repository.close()
