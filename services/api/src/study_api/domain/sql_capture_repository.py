"""PostgreSQL Capture and manual-correction repository."""

from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import MetaData, Table, create_engine, func, insert, select, update
from sqlalchemy.engine import Connection, Engine, RowMapping

from study_api.database import database_url
from study_api.domain.capture_repository import CaptureStateError, PendingCaptureUpload
from study_api.domain.learning_repository import ChildAssignmentError, ResourceVersionConflictError
from study_api.domain.models import (
    AuditEvent,
    Capture,
    CaptureCorrection,
    CaptureStatus,
    ConfirmCaptureUploadRequest,
    CorrectCaptureRequest,
    CreateCaptureRequest,
    StudySession,
)
from study_api.domain.repository import IdempotencyConflictError
from study_api.media_lifecycle import (
    CaptureObject,
    DeletionStatus,
    ExpiredCaptureObject,
    RetentionClass,
    retention_expires_at,
)


class PostgresCaptureRepository:
    """Transactional PostgreSQL implementation; Alembic owns the schema."""

    def __init__(self, url: str | None = None) -> None:
        self._engine = create_engine(url or database_url(), pool_pre_ping=True)
        metadata = MetaData()
        self._sessions = Table("study_sessions", metadata, autoload_with=self._engine)
        self._captures = Table("captures", metadata, autoload_with=self._engine)
        self._corrections = Table("capture_corrections", metadata, autoload_with=self._engine)
        self._idempotency = Table("idempotency_records", metadata, autoload_with=self._engine)
        self._audits = Table("audit_events", metadata, autoload_with=self._engine)

    @property
    def engine(self) -> Engine:
        return self._engine

    def close(self) -> None:
        self._engine.dispose()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _fingerprint(value: str) -> str:
        return sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _capture(row: RowMapping) -> Capture:
        return Capture.model_validate(dict(row))

    @staticmethod
    def _correction(row: RowMapping) -> CaptureCorrection:
        return CaptureCorrection.model_validate(dict(row))

    @staticmethod
    def _session(row: RowMapping) -> StudySession:
        return StudySession.model_validate(dict(row))

    def list_captures(self, household_id: UUID, session_id: UUID, child_id: UUID) -> list[Capture]:
        with self._engine.connect() as connection:
            self._session_for_child(connection, household_id, session_id, child_id)
            rows = connection.execute(
                select(self._captures)
                .where(
                    self._captures.c.household_id == household_id,
                    self._captures.c.session_id == session_id,
                )
                .order_by(self._captures.c.created_at, self._captures.c.id)
            ).mappings()
            return [self._capture(row) for row in rows]

    def create_capture(
        self,
        household_id: UUID,
        session_id: UUID,
        child_id: UUID,
        request: CreateCaptureRequest,
        idempotency_key: str,
    ) -> tuple[Capture, bool]:
        payload = request.model_dump_json()
        operation = f"create_capture:{session_id}"
        with self._engine.begin() as connection:
            self._session_for_child(connection, household_id, session_id, child_id)
            existing = self._idempotency_result(
                connection, household_id, operation, idempotency_key
            )
            if existing is not None:
                return self._replay_capture(connection, existing, payload)
            capture = Capture(
                id=uuid4(),
                household_id=household_id,
                child_id=child_id,
                session_id=session_id,
                media_type=request.media_type,
                byte_size=request.byte_size,
                content_sha256=request.content_sha256,
                status=CaptureStatus.NEEDS_CORRECTION,
                version=1,
                created_at=self._now(),
            )
            connection.execute(insert(self._captures).values(**capture.model_dump()))
            self._store_idempotency(
                connection, household_id, operation, idempotency_key, payload, "capture", capture.id
            )
            self._audit(connection, household_id, "capture_created", capture.id)
            return capture, False

    def begin_capture_upload(
        self,
        household_id: UUID,
        session_id: UUID,
        child_id: UUID,
        request: CreateCaptureRequest,
        idempotency_key: str,
    ) -> tuple[PendingCaptureUpload, bool]:
        payload = request.model_dump_json()
        operation = f"begin_capture_upload:{session_id}"
        with self._engine.begin() as connection:
            self._session_for_child(connection, household_id, session_id, child_id)
            existing = self._idempotency_result(
                connection, household_id, operation, idempotency_key
            )
            if existing is not None:
                pending, _ = self._replay_pending_capture(connection, existing, payload)
                if pending.capture.status is not CaptureStatus.UPLOAD_PENDING:
                    raise CaptureStateError
                return pending, True
            capture = Capture(
                id=uuid4(),
                household_id=household_id,
                child_id=child_id,
                session_id=session_id,
                media_type=request.media_type,
                byte_size=request.byte_size,
                content_sha256=request.content_sha256,
                status=CaptureStatus.UPLOAD_PENDING,
                version=1,
                created_at=self._now(),
            )
            pending = PendingCaptureUpload(capture, f"captures/{capture.id}/source")
            connection.execute(
                insert(self._captures).values(
                    **capture.model_dump(),
                    object_key=pending.object_key,
                    retention_class=RetentionClass.ORIGINAL.value,
                    expires_at=retention_expires_at(capture.created_at, RetentionClass.ORIGINAL),
                    deletion_status=DeletionStatus.ACTIVE.value,
                    parent_saved=False,
                )
            )
            self._store_idempotency(
                connection, household_id, operation, idempotency_key, payload, "capture", capture.id
            )
            self._audit(connection, household_id, "capture_upload_requested", capture.id)
            return pending, False

    def get_capture_upload(
        self, household_id: UUID, capture_id: UUID, child_id: UUID
    ) -> PendingCaptureUpload:
        with self._engine.connect() as connection:
            pending = self._pending_capture_for_child(
                connection, household_id, capture_id, child_id
            )
            return pending

    def get_capture(self, household_id: UUID, capture_id: UUID, child_id: UUID) -> Capture:
        with self._engine.connect() as connection:
            return self._capture_for_child(connection, household_id, capture_id, child_id)

    def confirm_capture_upload(
        self,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        request: ConfirmCaptureUploadRequest,
        idempotency_key: str,
    ) -> tuple[Capture, bool]:
        payload = request.model_dump_json()
        operation = f"confirm_capture_upload:{capture_id}"
        with self._engine.begin() as connection:
            capture = self._capture_for_child(connection, household_id, capture_id, child_id)
            existing = self._idempotency_result(
                connection, household_id, operation, idempotency_key
            )
            if existing is not None:
                return self._replay_capture(connection, existing, payload)
            if capture.version != request.expected_capture_version:
                raise ResourceVersionConflictError
            if capture.status is not CaptureStatus.UPLOAD_PENDING:
                raise CaptureStateError
            updated = connection.execute(
                update(self._captures)
                .where(
                    self._captures.c.id == capture_id,
                    self._captures.c.version == capture.version,
                    self._captures.c.status == CaptureStatus.UPLOAD_PENDING.value,
                )
                .values(status=CaptureStatus.NEEDS_CORRECTION.value, version=capture.version + 1)
            )
            if updated.rowcount != 1:
                raise ResourceVersionConflictError
            confirmed = capture.model_copy(
                update={"status": CaptureStatus.NEEDS_CORRECTION, "version": capture.version + 1}
            )
            self._store_idempotency(
                connection, household_id, operation, idempotency_key, payload, "capture", capture.id
            )
            self._audit(connection, household_id, "capture_upload_confirmed", capture.id)
            return confirmed, False

    def claim_expired_capture_objects(self, now: datetime) -> list[ExpiredCaptureObject]:
        with self._engine.begin() as connection:
            rows = (
                connection.execute(
                    select(self._captures.c.id, self._captures.c.object_key)
                    .where(
                        self._captures.c.object_key.is_not(None),
                        self._captures.c.expires_at <= now,
                        self._captures.c.parent_saved.is_(False),
                        self._captures.c.deletion_status.in_(
                            [DeletionStatus.ACTIVE.value, DeletionStatus.FAILED.value]
                        ),
                    )
                    .with_for_update(skip_locked=True)
                )
                .mappings()
                .all()
            )
            result = [
                ExpiredCaptureObject(capture_id=row["id"], object_key=row["object_key"])
                for row in rows
            ]
            for item in result:
                connection.execute(
                    update(self._captures)
                    .where(self._captures.c.id == item.capture_id)
                    .values(deletion_status=DeletionStatus.DELETING.value)
                )
            return result

    def claim_child_capture_objects(
        self, household_id: UUID, child_id: UUID
    ) -> list[CaptureObject]:
        """Atomically claim all object-backed captures for a child in one household."""

        with self._engine.begin() as connection:
            rows = (
                connection.execute(
                    select(self._captures.c.id, self._captures.c.object_key)
                    .where(
                        self._captures.c.household_id == household_id,
                        self._captures.c.child_id == child_id,
                        self._captures.c.object_key.is_not(None),
                        self._captures.c.deletion_status.in_(
                            [DeletionStatus.ACTIVE.value, DeletionStatus.FAILED.value]
                        ),
                    )
                    .order_by(self._captures.c.id)
                    .with_for_update(skip_locked=True)
                )
                .mappings()
                .all()
            )
            result = [
                CaptureObject(capture_id=row["id"], object_key=row["object_key"]) for row in rows
            ]
            for item in result:
                connection.execute(
                    update(self._captures)
                    .where(
                        self._captures.c.id == item.capture_id,
                        self._captures.c.deletion_status.in_(
                            [DeletionStatus.ACTIVE.value, DeletionStatus.FAILED.value]
                        ),
                    )
                    .values(deletion_status=DeletionStatus.DELETING.value)
                )
            return result

    def mark_capture_deleted(self, capture_id: UUID) -> None:
        with self._engine.begin() as connection:
            household_id = self._household_for_capture(connection, capture_id)
            connection.execute(
                update(self._captures)
                .where(self._captures.c.id == capture_id)
                .values(deletion_status=DeletionStatus.DELETED.value)
            )
            self._audit(connection, household_id, "capture_object_deleted", capture_id)

    def mark_capture_deletion_failed(self, capture_id: UUID) -> None:
        with self._engine.begin() as connection:
            household_id = self._household_for_capture(connection, capture_id)
            connection.execute(
                update(self._captures)
                .where(self._captures.c.id == capture_id)
                .values(deletion_status=DeletionStatus.FAILED.value)
            )
            self._audit(connection, household_id, "capture_object_deletion_failed", capture_id)

    def correct_capture(
        self,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        request: CorrectCaptureRequest,
        idempotency_key: str,
        *,
        operation_prefix: str = "correct_capture",
    ) -> tuple[CaptureCorrection, bool]:
        payload = request.model_dump_json()
        operation = f"{operation_prefix}:{capture_id}"
        with self._engine.begin() as connection:
            existing = self._idempotency_result(
                connection, household_id, operation, idempotency_key
            )
            if existing is not None:
                return self._replay_correction(connection, existing, payload)
            capture = self._capture_for_child(connection, household_id, capture_id, child_id)
            if capture.version != request.expected_capture_version:
                raise ResourceVersionConflictError
            if capture.status is not CaptureStatus.NEEDS_CORRECTION:
                raise CaptureStateError
            sequence = (
                connection.execute(
                    select(func.coalesce(func.max(self._corrections.c.sequence), 0)).where(
                        self._corrections.c.capture_id == capture_id
                    )
                ).scalar_one()
                + 1
            )
            correction = CaptureCorrection(
                id=uuid4(),
                capture_id=capture_id,
                household_id=household_id,
                child_id=child_id,
                sequence=sequence,
                corrected_text=request.corrected_text,
                created_at=self._now(),
            )
            updated = connection.execute(
                update(self._captures)
                .where(
                    self._captures.c.id == capture_id, self._captures.c.version == capture.version
                )
                .values(status=CaptureStatus.CORRECTED.value, version=capture.version + 1)
            )
            if updated.rowcount != 1:
                raise ResourceVersionConflictError
            connection.execute(insert(self._corrections).values(**correction.model_dump()))
            self._store_idempotency(
                connection,
                household_id,
                operation,
                idempotency_key,
                payload,
                "capture_correction",
                correction.id,
            )
            self._audit(connection, household_id, "capture_corrected", capture_id)
            return correction, False

    def save_capture(self, household_id: UUID, capture_id: UUID, idempotency_key: str) -> bool:
        payload = "capture-save:v1"
        operation = f"save_capture:{capture_id}"
        with self._engine.begin() as connection:
            row = self._capture_row_for_household(connection, household_id, capture_id)
            existing = self._idempotency_result(
                connection, household_id, operation, idempotency_key
            )
            if existing is not None:
                self._replay_capture(connection, existing, payload)
                return True
            if row["status"] == CaptureStatus.UPLOAD_PENDING.value or row["deletion_status"] in {
                DeletionStatus.DELETING.value,
                DeletionStatus.DELETED.value,
            }:
                raise CaptureStateError
            connection.execute(
                update(self._captures)
                .where(self._captures.c.id == capture_id)
                .values(parent_saved=True)
            )
            self._store_idempotency(
                connection, household_id, operation, idempotency_key, payload, "capture", capture_id
            )
            self._audit(connection, household_id, "capture_saved", capture_id)
            return False

    def begin_capture_deletion(
        self, household_id: UUID, capture_id: UUID, idempotency_key: str
    ) -> tuple[CaptureObject | None, bool]:
        payload = "capture-delete:v1"
        operation = f"delete_capture:{capture_id}"
        with self._engine.begin() as connection:
            row = self._capture_row_for_household(connection, household_id, capture_id)
            existing = self._idempotency_result(
                connection, household_id, operation, idempotency_key
            )
            if existing is not None:
                if (
                    existing["fingerprint"] != self._fingerprint(payload)
                    or existing["resource_type"] != "capture"
                ):
                    raise IdempotencyConflictError
                return None, True
            object_key = row["object_key"]
            state = row["deletion_status"]
            if object_key is None or state == DeletionStatus.DELETED.value:
                connection.execute(
                    update(self._captures)
                    .where(self._captures.c.id == capture_id)
                    .values(deletion_status=DeletionStatus.DELETED.value)
                )
                self._store_idempotency(
                    connection,
                    household_id,
                    operation,
                    idempotency_key,
                    payload,
                    "capture",
                    capture_id,
                )
                self._audit(connection, household_id, "capture_object_deleted", capture_id)
                return None, False
            if state not in {
                DeletionStatus.ACTIVE.value,
                DeletionStatus.FAILED.value,
                DeletionStatus.DELETING.value,
            }:
                raise CaptureStateError
            connection.execute(
                update(self._captures)
                .where(self._captures.c.id == capture_id)
                .values(deletion_status=DeletionStatus.DELETING.value)
            )
            return CaptureObject(capture_id=capture_id, object_key=object_key), False

    def complete_capture_deletion(
        self, household_id: UUID, capture_id: UUID, idempotency_key: str
    ) -> None:
        payload = "capture-delete:v1"
        operation = f"delete_capture:{capture_id}"
        with self._engine.begin() as connection:
            self._capture_row_for_household(connection, household_id, capture_id)
            existing = self._idempotency_result(
                connection, household_id, operation, idempotency_key
            )
            if existing is not None:
                if (
                    existing["fingerprint"] != self._fingerprint(payload)
                    or existing["resource_type"] != "capture"
                ):
                    raise IdempotencyConflictError
                return
            connection.execute(
                update(self._captures)
                .where(self._captures.c.id == capture_id)
                .values(deletion_status=DeletionStatus.DELETED.value)
            )
            self._store_idempotency(
                connection,
                household_id,
                operation,
                idempotency_key,
                payload,
                "capture",
                capture_id,
            )
            self._audit(connection, household_id, "capture_object_deleted", capture_id)

    def mark_capture_ocr_failed(self, household_id: UUID, capture_id: UUID) -> None:
        with self._engine.begin() as connection:
            row = self._capture_row_for_household(connection, household_id, capture_id)
            if row["deletion_status"] == DeletionStatus.DELETED.value:
                return
            if row["retention_class"] == RetentionClass.OCR_FAILURE.value:
                return
            connection.execute(
                update(self._captures)
                .where(
                    self._captures.c.id == capture_id,
                    self._captures.c.deletion_status != DeletionStatus.DELETED.value,
                )
                .values(
                    retention_class=RetentionClass.OCR_FAILURE.value,
                    expires_at=retention_expires_at(self._now(), RetentionClass.OCR_FAILURE),
                )
            )
            self._audit(connection, household_id, "capture_ocr_failed", capture_id)

    def _session_for_child(
        self, connection: Connection, household_id: UUID, session_id: UUID, child_id: UUID
    ) -> StudySession:
        row = (
            connection.execute(
                select(self._sessions)
                .where(
                    self._sessions.c.id == session_id,
                    self._sessions.c.household_id == household_id,
                )
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise LookupError
        session = self._session(row)
        if session.child_id != child_id:
            raise ChildAssignmentError
        return session

    def _capture_for_child(
        self, connection: Connection, household_id: UUID, capture_id: UUID, child_id: UUID
    ) -> Capture:
        row = (
            connection.execute(
                select(self._captures)
                .where(
                    self._captures.c.id == capture_id,
                    self._captures.c.household_id == household_id,
                )
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise LookupError
        capture = self._capture(row)
        if capture.child_id != child_id:
            raise ChildAssignmentError
        return capture

    def _capture_row_for_household(
        self, connection: Connection, household_id: UUID, capture_id: UUID
    ) -> RowMapping:
        row = (
            connection.execute(
                select(self._captures)
                .where(
                    self._captures.c.id == capture_id,
                    self._captures.c.household_id == household_id,
                )
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise LookupError
        return row

    def _pending_capture_for_child(
        self, connection: Connection, household_id: UUID, capture_id: UUID, child_id: UUID
    ) -> PendingCaptureUpload:
        row = (
            connection.execute(
                select(self._captures).where(
                    self._captures.c.id == capture_id,
                    self._captures.c.household_id == household_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise LookupError
        capture = self._capture(row)
        if capture.child_id != child_id:
            raise ChildAssignmentError
        object_key = row["object_key"]
        if object_key is None:
            raise CaptureStateError
        return PendingCaptureUpload(capture, object_key)

    def _household_for_capture(self, connection: Connection, capture_id: UUID) -> UUID:
        household_id = connection.execute(
            select(self._captures.c.household_id).where(self._captures.c.id == capture_id)
        ).scalar_one_or_none()
        if household_id is None:
            raise LookupError
        return household_id

    def _idempotency_result(
        self, connection: Connection, household_id: UUID, operation: str, key: str
    ) -> RowMapping | None:
        return (
            connection.execute(
                select(self._idempotency).where(
                    self._idempotency.c.household_id == household_id,
                    self._idempotency.c.operation == operation,
                    self._idempotency.c.idempotency_key == key,
                )
            )
            .mappings()
            .one_or_none()
        )

    def _store_idempotency(
        self,
        connection: Connection,
        household_id: UUID,
        operation: str,
        key: str,
        payload: str,
        resource_type: str,
        resource_id: UUID,
    ) -> None:
        connection.execute(
            insert(self._idempotency).values(
                household_id=household_id,
                operation=operation,
                idempotency_key=key,
                fingerprint=self._fingerprint(payload),
                resource_type=resource_type,
                resource_id=resource_id,
                created_at=self._now(),
            )
        )

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

    def _replay_capture(
        self, connection: Connection, record: RowMapping, payload: str
    ) -> tuple[Capture, bool]:
        if (
            record["fingerprint"] != self._fingerprint(payload)
            or record["resource_type"] != "capture"
        ):
            raise IdempotencyConflictError
        row = (
            connection.execute(
                select(self._captures).where(self._captures.c.id == record["resource_id"])
            )
            .mappings()
            .one()
        )
        return self._capture(row), True

    def _replay_pending_capture(
        self, connection: Connection, record: RowMapping, payload: str
    ) -> tuple[PendingCaptureUpload, bool]:
        if (
            record["fingerprint"] != self._fingerprint(payload)
            or record["resource_type"] != "capture"
        ):
            raise IdempotencyConflictError
        row = (
            connection.execute(
                select(self._captures).where(self._captures.c.id == record["resource_id"])
            )
            .mappings()
            .one()
        )
        object_key = row["object_key"]
        if object_key is None:
            raise CaptureStateError
        return PendingCaptureUpload(self._capture(row), object_key), True

    def _replay_correction(
        self, connection: Connection, record: RowMapping, payload: str
    ) -> tuple[CaptureCorrection, bool]:
        if (
            record["fingerprint"] != self._fingerprint(payload)
            or record["resource_type"] != "capture_correction"
        ):
            raise IdempotencyConflictError
        row = (
            connection.execute(
                select(self._corrections).where(self._corrections.c.id == record["resource_id"])
            )
            .mappings()
            .one()
        )
        return self._correction(row), True
