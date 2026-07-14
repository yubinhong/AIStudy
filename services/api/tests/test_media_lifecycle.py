from datetime import UTC, datetime, timedelta
from uuid import UUID

from study_api.media_lifecycle import (
    CaptureMediaCleanup,
    CaptureObject,
    CaptureObjectCascadeDeletion,
    DeletionStatus,
    ExpiredCaptureObject,
    RetentionClass,
    retention_expires_at,
)


def test_retention_windows_are_fixed_and_utc_normalized() -> None:
    created = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)

    assert retention_expires_at(created, RetentionClass.ORIGINAL) == created + timedelta(hours=24)
    assert retention_expires_at(created, RetentionClass.OCR_FAILURE) == created + timedelta(days=7)
    assert retention_expires_at(created, RetentionClass.CROP) == created + timedelta(days=30)
    assert retention_expires_at(created.replace(tzinfo=None), RetentionClass.ORIGINAL).tzinfo is UTC


class FakeCleanupRepository:
    def __init__(self) -> None:
        self.items = [
            ExpiredCaptureObject(UUID(int=1), "captures/synthetic/one"),
            ExpiredCaptureObject(UUID(int=2), "captures/synthetic/two"),
        ]
        self.status: dict[UUID, DeletionStatus] = {}

    def claim_expired_capture_objects(self, now: datetime) -> list[ExpiredCaptureObject]:
        for item in self.items:
            self.status[item.capture_id] = DeletionStatus.DELETING
        return self.items

    def mark_capture_deleted(self, capture_id: UUID) -> None:
        self.status[capture_id] = DeletionStatus.DELETED

    def mark_capture_deletion_failed(self, capture_id: UUID) -> None:
        self.status[capture_id] = DeletionStatus.FAILED


class FakeCleanupStorage:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def delete_object(self, object_key: str) -> None:
        self.deleted.append(object_key)
        if object_key.endswith("two"):
            raise RuntimeError("synthetic deletion failure")


class FakeChildCascadeRepository:
    def __init__(self) -> None:
        self.items = [
            CaptureObject(UUID(int=11), "captures/synthetic/child-one"),
            CaptureObject(UUID(int=12), "captures/synthetic/child-two"),
        ]
        self.status: dict[UUID, DeletionStatus] = {
            item.capture_id: DeletionStatus.ACTIVE for item in self.items
        }

    def claim_child_capture_objects(
        self, household_id: UUID, child_id: UUID
    ) -> list[CaptureObject]:
        assert household_id.int == 1
        assert child_id.int == 2
        claimed = [
            item
            for item in self.items
            if self.status[item.capture_id] in {DeletionStatus.ACTIVE, DeletionStatus.FAILED}
        ]
        for item in claimed:
            self.status[item.capture_id] = DeletionStatus.DELETING
        return claimed

    def mark_capture_deleted(self, capture_id: UUID) -> None:
        self.status[capture_id] = DeletionStatus.DELETED

    def mark_capture_deletion_failed(self, capture_id: UUID) -> None:
        self.status[capture_id] = DeletionStatus.FAILED


class RetryableChildCascadeStorage:
    def __init__(self) -> None:
        self.deleted: list[str] = []
        self.fail_once = True

    def delete_object(self, object_key: str) -> None:
        self.deleted.append(object_key)
        if object_key.endswith("child-two") and self.fail_once:
            self.fail_once = False
            raise RuntimeError("synthetic deletion failure")


def test_cleanup_marks_success_and_failure_without_leaking_object_keys() -> None:
    repository = FakeCleanupRepository()
    storage = FakeCleanupStorage()

    result = CaptureMediaCleanup(repository, storage).run_once(datetime(2026, 7, 14, tzinfo=UTC))

    assert result.claimed == 2
    assert result.deleted == 1
    assert result.failed == 1
    assert repository.status[UUID(int=1)] is DeletionStatus.DELETED
    assert repository.status[UUID(int=2)] is DeletionStatus.FAILED


def test_child_cascade_is_failure_visible_and_retryable() -> None:
    repository = FakeChildCascadeRepository()
    storage = RetryableChildCascadeStorage()
    cascade = CaptureObjectCascadeDeletion(repository, storage)

    first = cascade.run_once(UUID(int=1), UUID(int=2))
    second = cascade.run_once(UUID(int=1), UUID(int=2))

    assert first == type(first)(claimed=2, deleted=1, failed=1)
    assert second == type(second)(claimed=1, deleted=1, failed=0)
    assert repository.status == {
        UUID(int=11): DeletionStatus.DELETED,
        UUID(int=12): DeletionStatus.DELETED,
    }
