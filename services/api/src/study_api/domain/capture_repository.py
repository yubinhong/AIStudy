"""Capture and manual-correction repository for local/CI reference semantics."""

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol
from uuid import UUID, uuid4

from study_api.domain.learning_repository import ChildAssignmentError, ResourceVersionConflictError
from study_api.domain.models import (
    AuditEvent,
    Capture,
    CaptureCorrection,
    CaptureStatus,
    ConfirmCaptureUploadRequest,
    CorrectCaptureRequest,
    CreateCaptureRequest,
)
from study_api.domain.repository import IdempotencyConflictError
from study_api.domain.sql_learning_repository import LearningRepository
from study_api.media_lifecycle import (
    CaptureObject,
    DeletionStatus,
    RetentionClass,
    retention_expires_at,
)


class CaptureRepository(Protocol):
    def list_captures(
        self, household_id: UUID, session_id: UUID, child_id: UUID
    ) -> list[Capture]: ...

    def create_capture(
        self,
        household_id: UUID,
        session_id: UUID,
        child_id: UUID,
        request: CreateCaptureRequest,
        idempotency_key: str,
    ) -> tuple[Capture, bool]: ...

    def begin_capture_upload(
        self,
        household_id: UUID,
        session_id: UUID,
        child_id: UUID,
        request: CreateCaptureRequest,
        idempotency_key: str,
    ) -> tuple["PendingCaptureUpload", bool]: ...

    def get_capture_upload(
        self, household_id: UUID, capture_id: UUID, child_id: UUID
    ) -> "PendingCaptureUpload": ...

    def get_capture(self, household_id: UUID, capture_id: UUID, child_id: UUID) -> Capture: ...

    def confirm_capture_upload(
        self,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        request: ConfirmCaptureUploadRequest,
        idempotency_key: str,
    ) -> tuple[Capture, bool]: ...

    def correct_capture(
        self,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        request: CorrectCaptureRequest,
        idempotency_key: str,
        *,
        operation_prefix: str = "correct_capture",
    ) -> tuple[CaptureCorrection, bool]: ...

    def save_capture(self, household_id: UUID, capture_id: UUID, idempotency_key: str) -> bool: ...

    def begin_capture_deletion(
        self, household_id: UUID, capture_id: UUID, idempotency_key: str
    ) -> tuple[CaptureObject | None, bool]: ...

    def complete_capture_deletion(
        self, household_id: UUID, capture_id: UUID, idempotency_key: str
    ) -> None: ...

    def mark_capture_ocr_failed(self, household_id: UUID, capture_id: UUID) -> None: ...

    def claim_child_capture_objects(
        self, household_id: UUID, child_id: UUID
    ) -> list[CaptureObject]: ...

    def mark_capture_deleted(self, capture_id: UUID) -> None: ...

    def mark_capture_deletion_failed(self, capture_id: UUID) -> None: ...


@dataclass(frozen=True)
class StoredResult:
    fingerprint: str
    value: Capture | CaptureCorrection


@dataclass(frozen=True)
class PendingCaptureUpload:
    """Internal Capture state that pairs metadata with an unexposed object key."""

    capture: Capture
    object_key: str


class CaptureStateError(Exception):
    """Raised when a Capture transition does not match its current state."""


class InMemoryCaptureRepository:
    """Local/CI Capture semantics; never stores media bytes or logs correction text."""

    def __init__(self, learning_repository: LearningRepository) -> None:
        self._learning_repository = learning_repository
        self._captures: dict[UUID, Capture] = {}
        self._object_keys: dict[UUID, str] = {}
        self._corrections: dict[UUID, list[CaptureCorrection]] = {}
        self._deletion_status: dict[UUID, DeletionStatus] = {}
        self._retention_class: dict[UUID, RetentionClass] = {}
        self._expires_at: dict[UUID, datetime] = {}
        self._parent_saved: set[UUID] = set()
        self._idempotency: dict[tuple[UUID, str, str], StoredResult] = {}
        self._audits: list[AuditEvent] = []

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _fingerprint(value: str) -> str:
        return sha256(value.encode("utf-8")).hexdigest()

    def list_captures(self, household_id: UUID, session_id: UUID, child_id: UUID) -> list[Capture]:
        self._session_for_child(household_id, session_id, child_id)
        return sorted(
            (
                capture
                for capture in self._captures.values()
                if capture.household_id == household_id and capture.session_id == session_id
            ),
            key=lambda capture: (capture.created_at, capture.id),
        )

    def create_capture(
        self,
        household_id: UUID,
        session_id: UUID,
        child_id: UUID,
        request: CreateCaptureRequest,
        idempotency_key: str,
    ) -> tuple[Capture, bool]:
        self._session_for_child(household_id, session_id, child_id)
        payload = request.model_dump_json()
        key = (household_id, f"create_capture:{session_id}", idempotency_key)
        existing = self._idempotency.get(key)
        if existing is not None:
            if existing.fingerprint != self._fingerprint(payload):
                raise IdempotencyConflictError
            return self._as_capture(existing.value), True
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
        self._captures[capture.id] = capture
        self._deletion_status[capture.id] = DeletionStatus.ACTIVE
        self._retention_class[capture.id] = RetentionClass.ORIGINAL
        self._expires_at[capture.id] = retention_expires_at(
            capture.created_at, RetentionClass.ORIGINAL
        )
        self._idempotency[key] = StoredResult(self._fingerprint(payload), capture)
        self._audit(household_id, "capture_created", capture.id)
        return capture, False

    def begin_capture_upload(
        self,
        household_id: UUID,
        session_id: UUID,
        child_id: UUID,
        request: CreateCaptureRequest,
        idempotency_key: str,
    ) -> tuple[PendingCaptureUpload, bool]:
        self._session_for_child(household_id, session_id, child_id)
        payload = request.model_dump_json()
        key = (household_id, f"begin_capture_upload:{session_id}", idempotency_key)
        existing = self._idempotency.get(key)
        if existing is not None:
            if existing.fingerprint != self._fingerprint(payload):
                raise IdempotencyConflictError
            capture = self._as_capture(existing.value)
            current = self._captures[capture.id]
            if current.status is not CaptureStatus.UPLOAD_PENDING:
                raise CaptureStateError
            return PendingCaptureUpload(current, self._object_keys[current.id]), True
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
        self._captures[capture.id] = capture
        self._deletion_status[capture.id] = DeletionStatus.ACTIVE
        self._retention_class[capture.id] = RetentionClass.ORIGINAL
        self._expires_at[capture.id] = retention_expires_at(
            capture.created_at, RetentionClass.ORIGINAL
        )
        self._object_keys[capture.id] = f"captures/{capture.id}/source"
        self._idempotency[key] = StoredResult(self._fingerprint(payload), capture)
        self._audit(household_id, "capture_upload_requested", capture.id)
        return PendingCaptureUpload(capture, self._object_keys[capture.id]), False

    def get_capture_upload(
        self, household_id: UUID, capture_id: UUID, child_id: UUID
    ) -> PendingCaptureUpload:
        capture = self._capture_for_child(household_id, capture_id, child_id)
        object_key = self._object_keys.get(capture.id)
        if object_key is None:
            raise CaptureStateError
        return PendingCaptureUpload(capture, object_key)

    def get_capture(self, household_id: UUID, capture_id: UUID, child_id: UUID) -> Capture:
        return self._capture_for_child(household_id, capture_id, child_id)

    def confirm_capture_upload(
        self,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        request: ConfirmCaptureUploadRequest,
        idempotency_key: str,
    ) -> tuple[Capture, bool]:
        capture = self._capture_for_child(household_id, capture_id, child_id)
        payload = request.model_dump_json()
        key = (household_id, f"confirm_capture_upload:{capture_id}", idempotency_key)
        existing = self._idempotency.get(key)
        if existing is not None:
            if existing.fingerprint != self._fingerprint(payload):
                raise IdempotencyConflictError
            return self._as_capture(existing.value), True
        if capture.version != request.expected_capture_version:
            raise ResourceVersionConflictError
        if capture.status is not CaptureStatus.UPLOAD_PENDING:
            raise CaptureStateError
        confirmed = capture.model_copy(
            update={"status": CaptureStatus.NEEDS_CORRECTION, "version": capture.version + 1}
        )
        self._captures[capture_id] = confirmed
        self._idempotency[key] = StoredResult(self._fingerprint(payload), confirmed)
        self._audit(household_id, "capture_upload_confirmed", capture_id)
        return confirmed, False

    def claim_child_capture_objects(
        self, household_id: UUID, child_id: UUID
    ) -> list[CaptureObject]:
        result = [
            CaptureObject(capture_id=capture.id, object_key=self._object_keys[capture.id])
            for capture in self._captures.values()
            if capture.household_id == household_id
            and capture.child_id == child_id
            and capture.id in self._object_keys
            and self._deletion_status.get(capture.id, DeletionStatus.ACTIVE)
            in {DeletionStatus.ACTIVE, DeletionStatus.FAILED}
        ]
        result.sort(key=lambda item: item.capture_id)
        for item in result:
            self._deletion_status[item.capture_id] = DeletionStatus.DELETING
        return result

    def save_capture(self, household_id: UUID, capture_id: UUID, idempotency_key: str) -> bool:
        capture = self._capture_for_household(household_id, capture_id)
        payload = "capture-save:v1"
        key = (household_id, f"save_capture:{capture_id}", idempotency_key)
        existing = self._idempotency.get(key)
        if existing is not None:
            if existing.fingerprint != self._fingerprint(payload):
                raise IdempotencyConflictError
            self._as_capture(existing.value)
            return True
        if capture.status is CaptureStatus.UPLOAD_PENDING or self._deletion_status.get(
            capture_id
        ) in {
            DeletionStatus.DELETING,
            DeletionStatus.DELETED,
        }:
            raise CaptureStateError
        self._parent_saved.add(capture_id)
        self._idempotency[key] = StoredResult(self._fingerprint(payload), capture)
        self._audit(household_id, "capture_saved", capture_id)
        return False

    def begin_capture_deletion(
        self, household_id: UUID, capture_id: UUID, idempotency_key: str
    ) -> tuple[CaptureObject | None, bool]:
        capture = self._capture_for_household(household_id, capture_id)
        payload = "capture-delete:v1"
        key = (household_id, f"delete_capture:{capture_id}", idempotency_key)
        existing = self._idempotency.get(key)
        if existing is not None:
            if existing.fingerprint != self._fingerprint(payload):
                raise IdempotencyConflictError
            self._as_capture(existing.value)
            return None, True
        object_key = self._object_keys.get(capture_id)
        state = self._deletion_status.get(capture_id, DeletionStatus.ACTIVE)
        if object_key is None or state is DeletionStatus.DELETED:
            self._deletion_status[capture_id] = DeletionStatus.DELETED
            self._idempotency[key] = StoredResult(self._fingerprint(payload), capture)
            self._audit(household_id, "capture_object_deleted", capture_id)
            return None, False
        if state not in {DeletionStatus.ACTIVE, DeletionStatus.FAILED, DeletionStatus.DELETING}:
            raise CaptureStateError
        self._deletion_status[capture_id] = DeletionStatus.DELETING
        return CaptureObject(capture_id=capture_id, object_key=object_key), False

    def complete_capture_deletion(
        self, household_id: UUID, capture_id: UUID, idempotency_key: str
    ) -> None:
        capture = self._capture_for_household(household_id, capture_id)
        payload = "capture-delete:v1"
        key = (household_id, f"delete_capture:{capture_id}", idempotency_key)
        existing = self._idempotency.get(key)
        if existing is not None:
            if existing.fingerprint != self._fingerprint(payload):
                raise IdempotencyConflictError
            return
        self._deletion_status[capture_id] = DeletionStatus.DELETED
        self._idempotency[key] = StoredResult(self._fingerprint(payload), capture)
        self._audit(household_id, "capture_object_deleted", capture_id)

    def mark_capture_ocr_failed(self, household_id: UUID, capture_id: UUID) -> None:
        self._capture_for_household(household_id, capture_id)
        if self._deletion_status.get(capture_id) is DeletionStatus.DELETED:
            return
        if self._retention_class.get(capture_id) is RetentionClass.OCR_FAILURE:
            return
        self._retention_class[capture_id] = RetentionClass.OCR_FAILURE
        self._expires_at[capture_id] = retention_expires_at(self._now(), RetentionClass.OCR_FAILURE)
        self._audit(household_id, "capture_ocr_failed", capture_id)

    def mark_capture_deleted(self, capture_id: UUID) -> None:
        if capture_id not in self._captures:
            raise LookupError
        self._deletion_status[capture_id] = DeletionStatus.DELETED
        self._audit(self._captures[capture_id].household_id, "capture_object_deleted", capture_id)

    def mark_capture_deletion_failed(self, capture_id: UUID) -> None:
        if capture_id not in self._captures:
            raise LookupError
        self._deletion_status[capture_id] = DeletionStatus.FAILED
        self._audit(
            self._captures[capture_id].household_id,
            "capture_object_deletion_failed",
            capture_id,
        )

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
        capture = self._capture_for_child(household_id, capture_id, child_id)
        payload = request.model_dump_json()
        key = (household_id, f"{operation_prefix}:{capture_id}", idempotency_key)
        existing = self._idempotency.get(key)
        if existing is not None:
            if existing.fingerprint != self._fingerprint(payload):
                raise IdempotencyConflictError
            return self._as_correction(existing.value), True
        if capture.version != request.expected_capture_version:
            raise ResourceVersionConflictError
        if capture.status is not CaptureStatus.NEEDS_CORRECTION:
            raise CaptureStateError
        correction = CaptureCorrection(
            id=uuid4(),
            capture_id=capture_id,
            household_id=household_id,
            child_id=child_id,
            sequence=len(self._corrections.setdefault(capture_id, [])) + 1,
            corrected_text=request.corrected_text,
            created_at=self._now(),
        )
        self._corrections[capture_id].append(correction)
        self._captures[capture_id] = capture.model_copy(
            update={"status": CaptureStatus.CORRECTED, "version": capture.version + 1}
        )
        self._idempotency[key] = StoredResult(self._fingerprint(payload), correction)
        self._audit(household_id, "capture_corrected", capture_id)
        return correction, False

    def _session_for_child(self, household_id: UUID, session_id: UUID, child_id: UUID) -> None:
        session = self._learning_repository.get_session(household_id, session_id)
        if session is None:
            raise LookupError
        if session.child_id != child_id:
            raise ChildAssignmentError

    def _capture_for_child(self, household_id: UUID, capture_id: UUID, child_id: UUID) -> Capture:
        capture = self._captures.get(capture_id)
        if capture is None or capture.household_id != household_id:
            raise LookupError
        if capture.child_id != child_id:
            raise ChildAssignmentError
        return capture

    def _capture_for_household(self, household_id: UUID, capture_id: UUID) -> Capture:
        capture = self._captures.get(capture_id)
        if capture is None or capture.household_id != household_id:
            raise LookupError
        return capture

    def _audit(self, household_id: UUID, event_name: str, resource_id: UUID) -> None:
        self._audits.append(
            AuditEvent(
                id=uuid4(),
                household_id=household_id,
                event_name=event_name,
                resource_id=resource_id,
                recorded_at=self._now(),
            )
        )

    @staticmethod
    def _as_capture(value: Capture | CaptureCorrection) -> Capture:
        if not isinstance(value, Capture):
            raise TypeError("unexpected idempotency value")
        return value

    @staticmethod
    def _as_correction(value: Capture | CaptureCorrection) -> CaptureCorrection:
        if not isinstance(value, CaptureCorrection):
            raise TypeError("unexpected idempotency value")
        return value
