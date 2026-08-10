"""Atomic parent-facing child profile and child-account management."""

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import MetaData, Table, insert, select
from sqlalchemy.engine import Engine, RowMapping
from sqlalchemy.exc import IntegrityError

from study_api.auth_domain import (
    AccountRecord,
    AccountRepository,
    AccountRole,
    AuthService,
    CreateChildAccountRequest,
    CreateChildManagementRequest,
    DuplicateUsernameError,
    hash_password,
    normalize_username,
)
from study_api.database import database_url
from study_api.domain.models import ChildProfile, CreateChildRequest
from study_api.domain.repository import IdempotencyConflictError, ProfileRepository


@dataclass(frozen=True)
class ChildManagementRecord:
    child: ChildProfile
    account: AccountRecord | None


class ChildManagementRepository(Protocol):
    def list(self, household_id: UUID, owner_account_id: UUID) -> list[ChildManagementRecord]: ...

    def create(
        self,
        household_id: UUID,
        owner_account_id: UUID,
        request: CreateChildManagementRequest,
        idempotency_key: str,
    ) -> tuple[ChildManagementRecord, bool]: ...


class InMemoryChildManagementRepository:
    def __init__(
        self,
        profiles: ProfileRepository,
        accounts: AccountRepository,
        auth_service: AuthService,
    ) -> None:
        self._profiles = profiles
        self._accounts = accounts
        self._auth = auth_service

    def list(self, household_id: UUID, owner_account_id: UUID) -> list[ChildManagementRecord]:
        accounts = {
            account.child_id: account
            for account in self._accounts.list_household(household_id)
            if account.role is AccountRole.CHILD and account.child_id is not None
        }
        return [
            ChildManagementRecord(child, accounts.get(child.id))
            for child in self._profiles.list_children(
                household_id, owner_account_id=owner_account_id
            )
        ]

    def create(
        self,
        household_id: UUID,
        owner_account_id: UUID,
        request: CreateChildManagementRequest,
        idempotency_key: str,
    ) -> tuple[ChildManagementRecord, bool]:
        profile_request = CreateChildRequest(
            display_name=request.display_name,
            grade=request.grade,
            curriculum_version=request.curriculum_version,
            subjects=list(request.subjects),
        )
        child, profile_replayed = self._profiles.create_child(
            household_id,
            profile_request,
            f"aggregate-profile-{idempotency_key}",
            owner_account_id=owner_account_id,
        )
        try:
            if not profile_replayed and any(
                account.role is AccountRole.CHILD and account.child_id == child.id
                for account in self._accounts.list_household(household_id)
            ):
                raise DuplicateUsernameError("child account already exists")
            account_view, account_replayed = self._auth.create_child_account(
                household_id,
                CreateChildAccountRequest(
                    username=request.username,
                    password=request.password,
                    child_id=child.id,
                ),
                idempotency_key,
            )
            account = self._accounts.get(account_view.id)
        except Exception:
            if not profile_replayed:
                self._profiles.delete_child(
                    household_id, child.id, f"aggregate-rollback-{idempotency_key}"
                )
            raise
        return ChildManagementRecord(child, account), profile_replayed and account_replayed


class PostgresChildManagementRepository:
    """Single SQL transaction for profile, account, idempotency and audit rows."""

    def __init__(self, engine: Engine | None = None, url: str | None = None) -> None:
        from sqlalchemy import create_engine

        self._engine = engine or create_engine(url or database_url(), pool_pre_ping=True)
        metadata = MetaData()
        self._children = Table("child_profiles", metadata, autoload_with=self._engine)
        self._accounts = Table("accounts", metadata, autoload_with=self._engine)
        self._idempotency = Table("idempotency_records", metadata, autoload_with=self._engine)
        self._audits = Table("audit_events", metadata, autoload_with=self._engine)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _fingerprint(request: CreateChildManagementRequest) -> str:
        return sha256(request.model_dump_json().encode()).hexdigest()

    @staticmethod
    def _child(row: RowMapping) -> ChildProfile:
        return ChildProfile.model_validate(dict(row))

    @staticmethod
    def _account(row: RowMapping) -> AccountRecord:
        payload = dict(row)
        payload["role"] = AccountRole(payload["role"])
        return AccountRecord(**payload)

    def _record(self, connection, household_id: UUID, child_id: UUID) -> ChildManagementRecord:
        child_row = (
            connection.execute(
                select(self._children).where(
                    self._children.c.household_id == household_id,
                    self._children.c.id == child_id,
                )
            )
            .mappings()
            .one()
        )
        account_row = (
            connection.execute(
                select(self._accounts).where(
                    self._accounts.c.household_id == household_id,
                    self._accounts.c.child_id == child_id,
                    self._accounts.c.role == AccountRole.CHILD.value,
                )
            )
            .mappings()
            .one_or_none()
        )
        return ChildManagementRecord(
            self._child(child_row), self._account(account_row) if account_row else None
        )

    def list(self, household_id: UUID, owner_account_id: UUID) -> list[ChildManagementRecord]:
        with self._engine.connect() as connection:
            child_ids = connection.scalars(
                select(self._children.c.id)
                .where(
                    self._children.c.household_id == household_id,
                    self._children.c.owner_account_id == owner_account_id,
                )
                .order_by(self._children.c.created_at, self._children.c.id)
            )
            return [self._record(connection, household_id, child_id) for child_id in child_ids]

    def create(
        self,
        household_id: UUID,
        owner_account_id: UUID,
        request: CreateChildManagementRequest,
        idempotency_key: str,
    ) -> tuple[ChildManagementRecord, bool]:
        normalized_username = normalize_username(request.username)
        password_hash = hash_password(request.password, role=AccountRole.CHILD)
        operation = f"create_child_management:{household_id}"
        fingerprint = self._fingerprint(request)
        child_id = uuid4()
        account_id = uuid4()
        now = self._now()
        child = ChildProfile(
            id=child_id,
            household_id=household_id,
            owner_account_id=owner_account_id,
            display_name=request.display_name,
            grade=request.grade,
            curriculum_version=request.curriculum_version,
            subjects=list(request.subjects),
            created_at=now,
        )
        account = AccountRecord(
            id=account_id,
            household_id=household_id,
            username=normalized_username,
            role=AccountRole.CHILD,
            child_id=child_id,
            password_hash=password_hash,
            must_change_password=True,
            status="active",
            failed_login_count=0,
            locked_until=None,
            created_at=now,
            updated_at=now,
        )
        try:
            with self._engine.begin() as connection:
                existing = (
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
                if existing is not None:
                    if existing["fingerprint"] != fingerprint:
                        raise IdempotencyConflictError
                    return self._record(connection, household_id, existing["resource_id"]), True
                child_account_exists = connection.execute(
                    select(self._accounts.c.id).where(
                        self._accounts.c.household_id == household_id,
                        self._accounts.c.child_id == child_id,
                        self._accounts.c.role == AccountRole.CHILD.value,
                    )
                ).first()
                if child_account_exists is not None:
                    raise DuplicateUsernameError("child account already exists")
                connection.execute(
                    insert(self._children).values(
                        **child.model_dump(),
                        subjects=[subject.value for subject in child.subjects],
                        updated_at=now,
                    )
                )
                connection.execute(insert(self._accounts).values(**account.__dict__))
                connection.execute(
                    insert(self._idempotency).values(
                        household_id=household_id,
                        operation=operation,
                        idempotency_key=idempotency_key,
                        fingerprint=fingerprint,
                        resource_type="child_management",
                        resource_id=child_id,
                        created_at=now,
                    )
                )
                connection.execute(
                    insert(self._audits).values(
                        id=uuid4(),
                        household_id=household_id,
                        event_name="child_management_created",
                        resource_id=child_id,
                        recorded_at=now,
                    )
                )
        except IntegrityError as error:
            diagnostic = getattr(error.orig, "diag", None)
            if getattr(diagnostic, "constraint_name", None) in {
                "uq_accounts_household_username",
                "uq_accounts_household_child",
            }:
                raise DuplicateUsernameError("child account already exists") from error
            raise
        return ChildManagementRecord(child, account), False
