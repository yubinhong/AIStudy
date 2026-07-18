"""Transactional PostgreSQL persistence for household profiles and devices."""

from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import MetaData, Table, create_engine, delete, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection, Engine, RowMapping

from study_api.database import database_url
from study_api.domain.models import (
    AuditEvent,
    ChildProfile,
    CreateChildRequest,
    CreateDeviceRequest,
    Device,
    UpdateChildRequest,
)
from study_api.domain.repository import IdempotencyConflictError


class PostgresProfileRepository:
    """PostgreSQL is the sole profile/device fact source in durable mode."""

    def __init__(self, url: str | None = None) -> None:
        self._engine = create_engine(url or database_url(), pool_pre_ping=True)
        metadata = MetaData()
        self._children = Table("child_profiles", metadata, autoload_with=self._engine)
        self._devices = Table("devices", metadata, autoload_with=self._engine)
        self._idempotency = Table("idempotency_records", metadata, autoload_with=self._engine)
        self._audits = Table("audit_events", metadata, autoload_with=self._engine)
        self._tasks = Table("study_tasks", metadata, autoload_with=self._engine)
        self._study_sessions = Table("study_sessions", metadata, autoload_with=self._engine)
        self._attempts = Table("attempts", metadata, autoload_with=self._engine)
        self._captures = Table("captures", metadata, autoload_with=self._engine)
        self._capture_corrections = Table(
            "capture_corrections", metadata, autoload_with=self._engine
        )
        self._ocr_results = Table("ocr_results", metadata, autoload_with=self._engine)
        self._ocr_jobs = Table("ocr_jobs", metadata, autoload_with=self._engine)
        self._image_analysis_jobs = Table(
            "image_analysis_jobs", metadata, autoload_with=self._engine
        )
        self._question_extractions = Table(
            "question_extractions", metadata, autoload_with=self._engine
        )
        self._verified_questions = Table("verified_questions", metadata, autoload_with=self._engine)
        self._tutor_turns = Table("tutor_turns", metadata, autoload_with=self._engine)
        self._data_exports = Table("child_data_exports", metadata, autoload_with=self._engine)

    @property
    def engine(self) -> Engine:
        return self._engine

    def close(self) -> None:
        self._engine.dispose()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _fingerprint(payload: str) -> str:
        return sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _child(row: RowMapping) -> ChildProfile:
        return ChildProfile.model_validate(dict(row))

    @staticmethod
    def _device(row: RowMapping) -> Device:
        return Device.model_validate(dict(row))

    def list_children(self, household_id: UUID) -> list[ChildProfile]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                select(self._children)
                .where(self._children.c.household_id == household_id)
                .order_by(self._children.c.created_at, self._children.c.id)
            ).mappings()
            return [self._child(row) for row in rows]

    def get_child(self, household_id: UUID, child_id: UUID) -> ChildProfile | None:
        with self._engine.connect() as connection:
            row = self._child_row(connection, household_id, child_id)
        return self._child(row) if row is not None else None

    def create_child(
        self, household_id: UUID, request: CreateChildRequest, idempotency_key: str
    ) -> tuple[ChildProfile, bool]:
        payload = request.model_dump_json()
        child_id = uuid4()
        now = self._now()
        with self._engine.begin() as connection:
            created = self._reserve_idempotency(
                connection,
                household_id,
                "child",
                idempotency_key,
                payload,
                "child_profile",
                child_id,
            )
            if not created:
                return self._replay_child(
                    connection, household_id, "child", idempotency_key, payload
                )
            child = ChildProfile(
                id=child_id,
                household_id=household_id,
                display_name=request.display_name,
                grade=request.grade,
                curriculum_version=request.curriculum_version,
                subjects=request.subjects,
                created_at=now,
            )
            connection.execute(
                insert(self._children).values(
                    {
                        **child.model_dump(),
                        "subjects": [subject.value for subject in request.subjects],
                        "updated_at": now,
                    }
                )
            )
            self._audit(connection, household_id, "child_profile_created", child.id)
            return child, False

    def update_child(
        self,
        household_id: UUID,
        child_id: UUID,
        request: UpdateChildRequest,
        idempotency_key: str,
    ) -> tuple[ChildProfile | None, bool]:
        payload = request.model_dump_json()
        operation = f"child_update:{child_id}"
        with self._engine.begin() as connection:
            row = self._child_row(connection, household_id, child_id, for_update=True)
            if row is None:
                return None, False
            created = self._reserve_idempotency(
                connection,
                household_id,
                operation,
                idempotency_key,
                payload,
                "child_profile",
                child_id,
            )
            if not created:
                return self._replay_child(
                    connection, household_id, operation, idempotency_key, payload
                )
            connection.execute(
                update(self._children)
                .where(
                    self._children.c.id == child_id,
                    self._children.c.household_id == household_id,
                )
                .values(
                    display_name=request.display_name,
                    grade=request.grade,
                    curriculum_version=request.curriculum_version,
                    subjects=[subject.value for subject in request.subjects],
                    updated_at=self._now(),
                )
            )
            updated = ChildProfile(
                id=child_id,
                household_id=household_id,
                display_name=request.display_name,
                grade=request.grade,
                curriculum_version=request.curriculum_version,
                subjects=request.subjects,
                created_at=row["created_at"],
            )
            self._audit(connection, household_id, "child_profile_updated", child_id)
            return updated, False

    def delete_child(
        self, household_id: UUID, child_id: UUID, idempotency_key: str
    ) -> tuple[bool, bool]:
        payload = str(child_id)
        operation = f"child_delete:{child_id}"
        with self._engine.begin() as connection:
            if self._is_idempotency_replay(
                connection, household_id, operation, idempotency_key, payload, child_id
            ):
                return True, True
            row = self._child_row(connection, household_id, child_id, for_update=True)
            if row is None:
                # A concurrent delete can commit while this transaction waits for
                # the profile lock, so check the durable receipt once more.
                if self._is_idempotency_replay(
                    connection, household_id, operation, idempotency_key, payload, child_id
                ):
                    return True, True
                return False, False
            created = self._reserve_idempotency(
                connection,
                household_id,
                operation,
                idempotency_key,
                payload,
                "child_profile",
                child_id,
            )
            if not created:
                return True, True
            self._delete_child_learning_data(
                connection, household_id, child_id, keep_operation=operation
            )
            connection.execute(
                delete(self._children).where(
                    self._children.c.id == child_id,
                    self._children.c.household_id == household_id,
                )
            )
            self._audit(connection, household_id, "child_profile_deleted", child_id)
            return True, False

    def _delete_child_learning_data(
        self,
        connection: Connection,
        household_id: UUID,
        child_id: UUID,
        *,
        keep_operation: str,
    ) -> None:
        """Delete relational child data after object storage cleanup succeeded.

        Audit events intentionally remain append-only. Generic idempotency
        receipts for deleted resources are removed, except the current delete
        receipt which makes a retry observable and safe.
        """

        scoped_tables = (
            self._tasks,
            self._study_sessions,
            self._attempts,
            self._captures,
            self._ocr_results,
            self._ocr_jobs,
            self._image_analysis_jobs,
            self._question_extractions,
            self._verified_questions,
            self._tutor_turns,
            self._data_exports,
        )
        resource_ids: set[UUID] = {child_id}
        for table in scoped_tables:
            resource_ids.update(
                connection.scalars(
                    select(table.c.id).where(
                        table.c.household_id == household_id,
                        table.c.child_id == child_id,
                    )
                )
            )

        for table in (
            self._tutor_turns,
            self._data_exports,
            self._verified_questions,
            self._question_extractions,
            self._image_analysis_jobs,
            self._ocr_jobs,
            self._ocr_results,
            self._capture_corrections,
            self._captures,
            self._attempts,
            self._study_sessions,
            self._tasks,
        ):
            connection.execute(
                delete(table).where(
                    table.c.household_id == household_id,
                    table.c.child_id == child_id,
                )
            )
        if resource_ids:
            connection.execute(
                delete(self._idempotency).where(
                    self._idempotency.c.household_id == household_id,
                    self._idempotency.c.resource_id.in_(resource_ids),
                    self._idempotency.c.operation != keep_operation,
                )
            )

    def list_devices(self, household_id: UUID) -> list[Device]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                select(self._devices)
                .where(self._devices.c.household_id == household_id)
                .order_by(self._devices.c.registered_at, self._devices.c.id)
            ).mappings()
            return [self._device(row) for row in rows]

    def create_device(
        self, household_id: UUID, request: CreateDeviceRequest, idempotency_key: str
    ) -> tuple[Device, bool]:
        payload = request.model_dump_json()
        device_id = uuid4()
        now = self._now()
        with self._engine.begin() as connection:
            created = self._reserve_idempotency(
                connection,
                household_id,
                "device",
                idempotency_key,
                payload,
                "device",
                device_id,
            )
            if not created:
                return self._replay_device(connection, household_id, idempotency_key, payload)
            device = Device(
                id=device_id,
                household_id=household_id,
                kind=request.kind,
                platform=request.platform,
                display_name=request.display_name,
                registered_at=now,
            )
            connection.execute(
                insert(self._devices).values(
                    {
                        **device.model_dump(),
                        "kind": request.kind.value,
                        "platform": request.platform.value,
                    }
                )
            )
            self._audit(connection, household_id, "device_registered", device.id)
            return device, False

    def _child_row(
        self,
        connection: Connection,
        household_id: UUID,
        child_id: UUID,
        *,
        for_update: bool = False,
    ) -> RowMapping | None:
        statement = select(self._children).where(
            self._children.c.id == child_id,
            self._children.c.household_id == household_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return connection.execute(statement).mappings().one_or_none()

    def _reserve_idempotency(
        self,
        connection: Connection,
        household_id: UUID,
        operation: str,
        idempotency_key: str,
        payload: str,
        resource_type: str,
        resource_id: UUID,
    ) -> bool:
        fingerprint = self._fingerprint(payload)
        inserted = connection.execute(
            pg_insert(self._idempotency)
            .values(
                household_id=household_id,
                operation=operation,
                idempotency_key=idempotency_key,
                fingerprint=fingerprint,
                resource_type=resource_type,
                resource_id=resource_id,
                created_at=self._now(),
            )
            .on_conflict_do_nothing(index_elements=["household_id", "operation", "idempotency_key"])
            .returning(self._idempotency.c.resource_id)
        ).scalar_one_or_none()
        if inserted is not None:
            return True
        existing = self._idempotency_row(connection, household_id, operation, idempotency_key)
        if existing is None or existing["fingerprint"] != fingerprint:
            raise IdempotencyConflictError
        return False

    def _is_idempotency_replay(
        self,
        connection: Connection,
        household_id: UUID,
        operation: str,
        idempotency_key: str,
        payload: str,
        resource_id: UUID,
    ) -> bool:
        row = self._idempotency_row(connection, household_id, operation, idempotency_key)
        if row is None:
            return False
        if row["fingerprint"] != self._fingerprint(payload) or row["resource_id"] != resource_id:
            raise IdempotencyConflictError
        return True

    def _idempotency_row(
        self,
        connection: Connection,
        household_id: UUID,
        operation: str,
        idempotency_key: str,
    ) -> RowMapping | None:
        return (
            connection.execute(
                select(self._idempotency).where(
                    self._idempotency.c.household_id == household_id,
                    self._idempotency.c.operation == operation,
                    self._idempotency.c.idempotency_key == idempotency_key,
                )
            )
            .mappings()
            .one_or_none()
        )

    def _replay_child(
        self,
        connection: Connection,
        household_id: UUID,
        operation: str,
        idempotency_key: str,
        payload: str,
    ) -> tuple[ChildProfile, bool]:
        row = self._idempotency_row(connection, household_id, operation, idempotency_key)
        if row is None or row["fingerprint"] != self._fingerprint(payload):
            raise IdempotencyConflictError
        child_row = self._child_row(connection, household_id, row["resource_id"])
        if child_row is None:
            raise IdempotencyConflictError
        return self._child(child_row), True

    def _replay_device(
        self,
        connection: Connection,
        household_id: UUID,
        idempotency_key: str,
        payload: str,
    ) -> tuple[Device, bool]:
        row = self._idempotency_row(connection, household_id, "device", idempotency_key)
        if row is None or row["fingerprint"] != self._fingerprint(payload):
            raise IdempotencyConflictError
        device_row = (
            connection.execute(
                select(self._devices).where(
                    self._devices.c.id == row["resource_id"],
                    self._devices.c.household_id == household_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if device_row is None:
            raise IdempotencyConflictError
        return self._device(device_row), True

    def _audit(
        self, connection: Connection, household_id: UUID, event_name: str, resource_id: UUID
    ) -> None:
        event = AuditEvent(
            id=uuid4(),
            household_id=household_id,
            event_name=event_name,
            resource_id=resource_id,
            recorded_at=self._now(),
        )
        connection.execute(insert(self._audits).values(**event.model_dump()))
