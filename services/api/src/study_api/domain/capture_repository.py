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
    CorrectCaptureRequest,
    CreateCaptureRequest,
)
from study_api.domain.repository import IdempotencyConflictError
from study_api.domain.sql_learning_repository import LearningRepository


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

    def correct_capture(
        self,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        request: CorrectCaptureRequest,
        idempotency_key: str,
    ) -> tuple[CaptureCorrection, bool]: ...


@dataclass(frozen=True)
class StoredResult:
    fingerprint: str
    value: Capture | CaptureCorrection


class InMemoryCaptureRepository:
    """Local/CI Capture semantics; never stores media bytes or logs correction text."""

    def __init__(self, learning_repository: LearningRepository) -> None:
        self._learning_repository = learning_repository
        self._captures: dict[UUID, Capture] = {}
        self._corrections: dict[UUID, list[CaptureCorrection]] = {}
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
        self._idempotency[key] = StoredResult(self._fingerprint(payload), capture)
        self._audit(household_id, "capture_created", capture.id)
        return capture, False

    def correct_capture(
        self,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        request: CorrectCaptureRequest,
        idempotency_key: str,
    ) -> tuple[CaptureCorrection, bool]:
        capture = self._capture_for_child(household_id, capture_id, child_id)
        payload = request.model_dump_json()
        key = (household_id, f"correct_capture:{capture_id}", idempotency_key)
        existing = self._idempotency.get(key)
        if existing is not None:
            if existing.fingerprint != self._fingerprint(payload):
                raise IdempotencyConflictError
            return self._as_correction(existing.value), True
        if capture.version != request.expected_capture_version:
            raise ResourceVersionConflictError
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
