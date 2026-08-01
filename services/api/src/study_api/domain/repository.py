"""In-memory synthetic repository used only for local/CI vertical-slice tests."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol, TypeVar, cast
from uuid import UUID, uuid4

from study_api.domain.models import (
    AuditEvent,
    ChildProfile,
    CreateChildRequest,
    CreateDeviceRequest,
    Device,
    DeviceKind,
    DevicePlatform,
    Subject,
    UpdateChildRequest,
)

T = TypeVar("T", ChildProfile, Device)

HOUSEHOLD_A = UUID("00000000-0000-0000-0000-000000000001")
HOUSEHOLD_B = UUID("00000000-0000-0000-0000-000000000002")
SYNTHETIC_OWNER_ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000001")


class IdempotencyConflictError(Exception):
    """Raised when a key is reused with a different request payload."""


class ProfileRepository(Protocol):
    """Household-scoped profile and device persistence boundary."""

    def list_children(
        self, household_id: UUID, *, owner_account_id: UUID | None = None
    ) -> list[ChildProfile]: ...

    def get_child(self, household_id: UUID, child_id: UUID) -> ChildProfile | None: ...

    def create_child(
        self,
        household_id: UUID,
        request: CreateChildRequest,
        idempotency_key: str,
        *,
        owner_account_id: UUID | None = None,
    ) -> tuple[ChildProfile, bool]: ...

    def update_child(
        self,
        household_id: UUID,
        child_id: UUID,
        request: UpdateChildRequest,
        idempotency_key: str,
    ) -> tuple[ChildProfile | None, bool]: ...

    def delete_child(
        self, household_id: UUID, child_id: UUID, idempotency_key: str
    ) -> tuple[bool, bool]: ...

    def list_devices(self, household_id: UUID) -> list[Device]: ...

    def create_device(
        self, household_id: UUID, request: CreateDeviceRequest, idempotency_key: str
    ) -> tuple[Device, bool]: ...


@dataclass(frozen=True)
class IdempotencyRecord:
    fingerprint: str
    value: ChildProfile | Device


class InMemoryProfileRepository:
    """Synthetic store; it is intentionally not a PostgreSQL replacement."""

    def __init__(self) -> None:
        self._children: dict[UUID, ChildProfile] = {}
        self._devices: dict[UUID, Device] = {}
        self._idempotency: dict[tuple[UUID, str, str], IdempotencyRecord] = {}
        self._delete_idempotency: set[tuple[UUID, UUID, str]] = set()
        self._audits: list[AuditEvent] = []
        self._seed()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def _seed(self) -> None:
        created_at = datetime(2026, 1, 1, tzinfo=UTC)
        self._children[UUID("00000000-0000-0000-0000-000000000101")] = ChildProfile(
            id=UUID("00000000-0000-0000-0000-000000000101"),
            household_id=HOUSEHOLD_A,
            owner_account_id=UUID("00000000-0000-0000-0000-000000000001"),
            display_name="Synthetic Child A",
            grade=3,
            curriculum_version="math-demo-2026",
            subjects=[Subject.MATH],
            created_at=created_at,
        )
        self._children[UUID("00000000-0000-0000-0000-000000000102")] = ChildProfile(
            id=UUID("00000000-0000-0000-0000-000000000102"),
            household_id=HOUSEHOLD_B,
            owner_account_id=UUID("00000000-0000-0000-0000-000000000002"),
            display_name="Synthetic Child B",
            grade=4,
            curriculum_version="math-demo-2026",
            subjects=[Subject.MATH],
            created_at=created_at,
        )
        self._devices[UUID("00000000-0000-0000-0000-000000000201")] = Device(
            id=UUID("00000000-0000-0000-0000-000000000201"),
            household_id=HOUSEHOLD_A,
            kind=DeviceKind.CHILD,
            platform=DevicePlatform.IOS,
            display_name="Synthetic iPad",
            registered_at=created_at,
        )

    def list_children(
        self, household_id: UUID, *, owner_account_id: UUID | None = None
    ) -> list[ChildProfile]:
        return sorted(
            (
                child
                for child in self._children.values()
                if child.household_id == household_id
                and (owner_account_id is None or child.owner_account_id == owner_account_id)
            ),
            key=lambda child: child.created_at,
        )

    def get_child(self, household_id: UUID, child_id: UUID) -> ChildProfile | None:
        child = self._children.get(child_id)
        return child if child and child.household_id == household_id else None

    def delete_child(
        self, household_id: UUID, child_id: UUID, idempotency_key: str
    ) -> tuple[bool, bool]:
        """Delete one synthetic profile only after media cascade succeeds."""

        key = (household_id, child_id, idempotency_key)
        if key in self._delete_idempotency:
            return True, True
        child = self.get_child(household_id, child_id)
        if child is None:
            return False, False
        del self._children[child_id]
        self._delete_idempotency.add(key)
        self._audits.append(
            AuditEvent(
                id=uuid4(),
                household_id=household_id,
                event_name="child_profile_deleted",
                resource_id=child_id,
                recorded_at=self._now(),
            )
        )
        return True, False

    def create_child(
        self,
        household_id: UUID,
        request: CreateChildRequest,
        idempotency_key: str,
        *,
        owner_account_id: UUID | None = None,
    ) -> tuple[ChildProfile, bool]:
        return self._create(
            household_id,
            "child",
            request.model_dump_json(),
            idempotency_key,
            lambda: ChildProfile(
                id=uuid4(),
                household_id=household_id,
                owner_account_id=owner_account_id or SYNTHETIC_OWNER_ACCOUNT_ID,
                display_name=request.display_name,
                grade=request.grade,
                curriculum_version=request.curriculum_version,
                subjects=request.subjects,
                created_at=self._now(),
            ),
            self._children,
        )

    def update_child(
        self,
        household_id: UUID,
        child_id: UUID,
        request: UpdateChildRequest,
        idempotency_key: str,
    ) -> tuple[ChildProfile | None, bool]:
        existing = self.get_child(household_id, child_id)
        if existing is None:
            return None, False
        updated, replayed = self._create(
            household_id,
            f"child_update:{child_id}",
            request.model_dump_json(),
            idempotency_key,
            lambda: ChildProfile(
                id=child_id,
                household_id=household_id,
                owner_account_id=existing.owner_account_id,
                display_name=request.display_name,
                grade=request.grade,
                curriculum_version=request.curriculum_version,
                subjects=request.subjects,
                created_at=existing.created_at,
            ),
            self._children,
        )
        return updated, replayed

    def list_devices(self, household_id: UUID) -> list[Device]:
        return sorted(
            (device for device in self._devices.values() if device.household_id == household_id),
            key=lambda device: device.registered_at,
        )

    def create_device(
        self, household_id: UUID, request: CreateDeviceRequest, idempotency_key: str
    ) -> tuple[Device, bool]:
        return self._create(
            household_id,
            "device",
            request.model_dump_json(),
            idempotency_key,
            lambda: Device(
                id=uuid4(),
                household_id=household_id,
                kind=request.kind,
                platform=request.platform,
                display_name=request.display_name,
                registered_at=self._now(),
            ),
            self._devices,
        )

    def _create(
        self,
        household_id: UUID,
        operation: str,
        payload: str,
        idempotency_key: str,
        factory: Callable[[], T],
        collection: dict[UUID, T],
    ) -> tuple[T, bool]:
        fingerprint = sha256(payload.encode("utf-8")).hexdigest()
        key = (household_id, operation, idempotency_key)
        existing = self._idempotency.get(key)
        if existing:
            if existing.fingerprint != fingerprint:
                raise IdempotencyConflictError
            return cast(T, existing.value), True
        value = factory()
        collection[value.id] = value
        self._idempotency[key] = IdempotencyRecord(fingerprint=fingerprint, value=value)
        return value, False
