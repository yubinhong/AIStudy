"""Approved Capture media retention policy and deletion orchestration."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class RetentionClass(StrEnum):
    ORIGINAL = "original"
    OCR_FAILURE = "ocr_failure"
    CROP = "crop"


class DeletionStatus(StrEnum):
    ACTIVE = "active"
    DELETING = "deleting"
    DELETED = "deleted"
    FAILED = "failed"


_RETENTION_WINDOWS = {
    RetentionClass.ORIGINAL: timedelta(hours=24),
    RetentionClass.OCR_FAILURE: timedelta(days=7),
    RetentionClass.CROP: timedelta(days=30),
}


def retention_expires_at(created_at: datetime, retention_class: RetentionClass) -> datetime:
    """Return a fixed upper bound; caller cannot silently extend it."""

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return created_at.astimezone(UTC) + _RETENTION_WINDOWS[retention_class]


@dataclass(frozen=True)
class CaptureObject:
    capture_id: UUID
    object_key: str


ExpiredCaptureObject = CaptureObject


class CleanupRepository(Protocol):
    def claim_expired_capture_objects(self, now: datetime) -> list[ExpiredCaptureObject]: ...

    def mark_capture_deleted(self, capture_id: UUID) -> None: ...

    def mark_capture_deletion_failed(self, capture_id: UUID) -> None: ...


class DeletableObjectStorage(Protocol):
    def delete_object(self, object_key: str) -> None: ...


class ChildCaptureCascadeRepository(Protocol):
    """Repository boundary for a parent-approved child data deletion job."""

    def claim_child_capture_objects(
        self, household_id: UUID, child_id: UUID
    ) -> list[CaptureObject]: ...

    def mark_capture_deleted(self, capture_id: UUID) -> None: ...

    def mark_capture_deletion_failed(self, capture_id: UUID) -> None: ...


class SingleCaptureDeletionRepository(Protocol):
    def begin_capture_deletion(
        self, household_id: UUID, capture_id: UUID, idempotency_key: str
    ) -> tuple[CaptureObject | None, bool]: ...

    def complete_capture_deletion(
        self, household_id: UUID, capture_id: UUID, idempotency_key: str
    ) -> None: ...

    def mark_capture_deletion_failed(self, capture_id: UUID) -> None: ...


@dataclass(frozen=True)
class CleanupResult:
    claimed: int
    deleted: int
    failed: int


class CaptureMediaCleanup:
    """Delete expired private objects without logging their keys."""

    def __init__(
        self, repository: CleanupRepository, object_storage: DeletableObjectStorage
    ) -> None:
        self._repository = repository
        self._object_storage = object_storage

    def run_once(self, now: datetime | None = None) -> CleanupResult:
        effective_now = now or datetime.now(UTC)
        expired = self._repository.claim_expired_capture_objects(effective_now)
        deleted = 0
        failed = 0
        for item in expired:
            try:
                self._object_storage.delete_object(item.object_key)
            except Exception:  # noqa: BLE001 -- mark failure and allow bounded retry.
                self._repository.mark_capture_deletion_failed(item.capture_id)
                failed += 1
            else:
                self._repository.mark_capture_deleted(item.capture_id)
                deleted += 1
        return CleanupResult(claimed=len(expired), deleted=deleted, failed=failed)


class CaptureObjectCascadeDeletion:
    """Delete all private Capture objects belonging to one child.

    The repository claims only rows inside the requested household and child
    boundary. Each object is deleted independently so a transient storage
    failure leaves a visible, retryable FAILED state instead of reporting a
    misleading all-done result.
    """

    def __init__(
        self,
        repository: ChildCaptureCascadeRepository,
        object_storage: DeletableObjectStorage,
    ) -> None:
        self._repository = repository
        self._object_storage = object_storage

    def run_once(self, household_id: UUID, child_id: UUID) -> CleanupResult:
        claimed_objects = self._repository.claim_child_capture_objects(household_id, child_id)
        deleted = 0
        failed = 0
        for item in claimed_objects:
            try:
                self._object_storage.delete_object(item.object_key)
            except Exception:  # noqa: BLE001 -- persist failure for bounded retry.
                self._repository.mark_capture_deletion_failed(item.capture_id)
                failed += 1
            else:
                self._repository.mark_capture_deleted(item.capture_id)
                deleted += 1
        return CleanupResult(claimed=len(claimed_objects), deleted=deleted, failed=failed)


class SingleCaptureObjectDeletion:
    """Delete one parent-selected Capture object with retryable state."""

    def __init__(
        self,
        repository: SingleCaptureDeletionRepository,
        object_storage: DeletableObjectStorage,
    ) -> None:
        self._repository = repository
        self._object_storage = object_storage

    def run_once(
        self, household_id: UUID, capture_id: UUID, idempotency_key: str
    ) -> tuple[bool, bool]:
        claimed, replayed = self._repository.begin_capture_deletion(
            household_id, capture_id, idempotency_key
        )
        if replayed:
            return True, True
        if claimed is not None:
            try:
                self._object_storage.delete_object(claimed.object_key)
            except Exception:  # noqa: BLE001 -- persist failure for bounded retry.
                self._repository.mark_capture_deletion_failed(capture_id)
                raise
        self._repository.complete_capture_deletion(household_id, capture_id, idempotency_key)
        return True, False
