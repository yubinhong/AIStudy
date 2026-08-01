"""Account/password and opaque-session domain for the self-hosted deployment."""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Protocol
from unicodedata import normalize
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from argon2 import PasswordHasher
from argon2.exceptions import HashingError, VerificationError, VerifyMismatchError
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import MetaData, Table, create_engine, delete, insert, select, update
from sqlalchemy.engine import Engine, RowMapping
from sqlalchemy.exc import IntegrityError

from study_api.database import database_url
from study_api.domain.models import AccountRole, AuditEvent, ChildProfile, Subject
from study_api.domain.repository import IdempotencyConflictError, ProfileRepository

DEFAULT_HOUSEHOLD_ID = UUID("00000000-0000-0000-0000-000000000001")
BOOTSTRAP_USERNAME = "admin"
BOOTSTRAP_PASSWORD = "admin123456"
SESSION_TTL = timedelta(days=30)
LOCKOUT_AFTER_FAILURES = 5
LOCKOUT_FOR = timedelta(minutes=15)
ANONYMOUS_RESOURCE_ID = UUID("00000000-0000-0000-0000-000000000000")
BOOTSTRAP_ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000001")

# Explicit parameters make the password-cost contract reviewable and stable.
PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


class AuthError(Exception):
    """Expected authentication failure; callers expose one stable message."""


class PasswordPolicyError(ValueError):
    pass


class DuplicateUsernameError(ValueError):
    """The normalized username is already allocated."""


def normalize_username(value: str) -> str:
    normalized = normalize("NFKC", value).strip().casefold()
    if not 3 <= len(normalized) <= 80 or any(
        character.isspace() or ord(character) < 0x21 for character in normalized
    ):
        raise PasswordPolicyError("username is invalid")
    return normalized


def validate_password(value: str, *, role: AccountRole) -> str:
    minimum = 12 if role in {AccountRole.PARENT, AccountRole.SUPER_ADMIN} else 8
    if not minimum <= len(value) <= 128:
        raise PasswordPolicyError("password length is invalid")
    if any(ord(character) < 0x20 for character in value):
        raise PasswordPolicyError("password contains invalid characters")
    return value


def hash_password(password: str, *, role: AccountRole) -> str:
    return PASSWORD_HASHER.hash(validate_password(password, role=role))


def hash_bootstrap_password() -> str:
    """Hash the ADR bootstrap secret; it is invalidated before data access."""

    return PASSWORD_HASHER.hash(BOOTSTRAP_PASSWORD)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(password_hash, password)
    except (VerificationError, VerifyMismatchError, HashingError):
        return False


@dataclass(frozen=True)
class AccountRecord:
    id: UUID
    household_id: UUID
    username: str
    role: AccountRole
    child_id: UUID | None
    password_hash: str
    must_change_password: bool
    status: str
    failed_login_count: int
    locked_until: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class SessionRecord:
    id: UUID
    account_id: UUID
    household_id: UUID
    token_digest: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


class AccountView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    household_id: UUID
    username: str
    role: AccountRole
    child_id: UUID | None
    must_change_password: bool
    status: str
    created_at: datetime


class FamilyParentView(BaseModel):
    """One ordinary parent provisioned for an isolated family."""

    model_config = ConfigDict(frozen=True)

    account: AccountView
    child_count: int = Field(ge=0)


class CreateChildManagementRequest(BaseModel):
    """One parent command for a child profile and its unique login account."""

    display_name: str = Field(min_length=1, max_length=80)
    grade: int = Field(ge=1, le=6)
    curriculum_version: str = Field(min_length=1, max_length=80)
    subjects: list[Subject] = Field(min_length=1)
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1, max_length=128)


class ChildManagementView(BaseModel):
    child: ChildProfile
    account: AccountView | None = None


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1, max_length=128)
    client: str = Field(default="web", pattern=r"^(web|flutter)$")


class LoginResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    account: AccountView
    access_token: str | None = None
    expires_at: datetime


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class CreateChildAccountRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1, max_length=128)
    child_id: UUID


class CreateParentAccountRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1, max_length=128)


class CreateHouseholdRequest(BaseModel):
    """Provision one isolated family and its first ordinary parent."""

    parent_username: str = Field(min_length=3, max_length=80)
    parent_password: str = Field(min_length=1, max_length=128)


class SetAccountStatusRequest(BaseModel):
    enabled: bool
    current_password: str = Field(min_length=1, max_length=128)


class ResetPasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class DeleteParentAccountRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)


def _view(account: AccountRecord) -> AccountView:
    return AccountView(
        id=account.id,
        household_id=account.household_id,
        username=account.username,
        role=account.role,
        child_id=account.child_id,
        must_change_password=account.must_change_password,
        status=account.status,
        created_at=account.created_at,
    )


class AccountRepository(Protocol):
    def ensure_bootstrap(self, household_id: UUID = DEFAULT_HOUSEHOLD_ID) -> AccountRecord: ...

    def get_by_username(self, username: str) -> AccountRecord | None: ...

    def get(self, account_id: UUID) -> AccountRecord: ...

    def create_child(
        self,
        household_id: UUID,
        username: str,
        password_hash: str,
        child_id: UUID,
        idempotency_key: str,
        fingerprint: str,
    ) -> tuple[AccountRecord, bool]: ...

    def create_parent(
        self,
        household_id: UUID,
        username: str,
        password_hash: str,
        role: AccountRole,
        idempotency_key: str,
        fingerprint: str,
    ) -> tuple[AccountRecord, bool]: ...

    def list_household(self, household_id: UUID) -> list[AccountRecord]: ...

    def list_parent_accounts(self) -> list[AccountRecord]: ...

    def delete_child_account(self, household_id: UUID, child_id: UUID) -> None: ...

    def delete_parent_account(self, account_id: UUID) -> None: ...

    def set_login_failure(self, account_id: UUID, now: datetime) -> None: ...

    def clear_login_failures(self, account_id: UUID) -> None: ...

    def set_password(
        self, account_id: UUID, password_hash: str, must_change_password: bool
    ) -> AccountRecord: ...

    def set_status(self, account_id: UUID, enabled: bool) -> AccountRecord: ...

    def create_session(
        self, account: AccountRecord, token_digest: str, created_at: datetime, expires_at: datetime
    ) -> SessionRecord: ...

    def get_session(self, token_digest: str) -> SessionRecord | None: ...

    def revoke_session(self, session_id: UUID, now: datetime) -> None: ...

    def revoke_account_sessions(self, account_id: UUID, now: datetime) -> None: ...

    def record_audit_event(
        self, household_id: UUID, event_name: str, resource_id: UUID, recorded_at: datetime
    ) -> AuditEvent: ...


class InMemoryAccountRepository:
    def __init__(self, household_id: UUID = DEFAULT_HOUSEHOLD_ID) -> None:
        self._accounts: dict[UUID, AccountRecord] = {}
        self._sessions: dict[UUID, SessionRecord] = {}
        self._idempotency: dict[tuple[UUID, str, str], tuple[str, UUID]] = {}
        self._audit_events: list[AuditEvent] = []
        self.ensure_bootstrap(household_id)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def ensure_bootstrap(self, household_id: UUID = DEFAULT_HOUSEHOLD_ID) -> AccountRecord:
        if self._accounts:
            return next(iter(self._accounts.values()))
        now = self._now()
        account = AccountRecord(
            id=BOOTSTRAP_ACCOUNT_ID,
            household_id=household_id,
            username=BOOTSTRAP_USERNAME,
            role=AccountRole.SUPER_ADMIN,
            child_id=None,
            password_hash=hash_bootstrap_password(),
            must_change_password=True,
            status="active",
            failed_login_count=0,
            locked_until=None,
            created_at=now,
            updated_at=now,
        )
        self._accounts[account.id] = account
        return account

    def get_by_username(self, username: str) -> AccountRecord | None:
        normalized = normalize_username(username)
        return next((item for item in self._accounts.values() if item.username == normalized), None)

    def get(self, account_id: UUID) -> AccountRecord:
        account = self._accounts.get(account_id)
        if account is None:
            raise LookupError
        return account

    def create_child(
        self,
        household_id: UUID,
        username: str,
        password_hash: str,
        child_id: UUID,
        idempotency_key: str,
        fingerprint: str,
    ) -> tuple[AccountRecord, bool]:
        operation = f"create_child_account:{household_id}"
        key = (household_id, operation, idempotency_key)
        replay = self._idempotency.get(key)
        if replay is not None:
            if replay[0] != fingerprint:
                raise IdempotencyConflictError
            return self.get(replay[1]), True
        normalized = normalize_username(username)
        if self.get_by_username(normalized) is not None:
            raise DuplicateUsernameError("username already exists")
        now = self._now()
        account = AccountRecord(
            id=uuid4(),
            household_id=household_id,
            username=normalized,
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
        self._accounts[account.id] = account
        self._idempotency[key] = (fingerprint, account.id)
        return account, False

    def create_parent(
        self,
        household_id: UUID,
        username: str,
        password_hash: str,
        role: AccountRole,
        idempotency_key: str,
        fingerprint: str,
    ) -> tuple[AccountRecord, bool]:
        if role not in {AccountRole.PARENT, AccountRole.SUPER_ADMIN}:
            raise ValueError("parent account role is required")
        operation = f"create_parent_account:{household_id}"
        key = (household_id, operation, idempotency_key)
        replay = self._idempotency.get(key)
        if replay is not None:
            if replay[0] != fingerprint:
                raise IdempotencyConflictError
            return self.get(replay[1]), True
        normalized = normalize_username(username)
        if self.get_by_username(normalized) is not None:
            raise DuplicateUsernameError("username already exists")
        now = self._now()
        account = AccountRecord(
            id=uuid4(),
            household_id=household_id,
            username=normalized,
            role=role,
            child_id=None,
            password_hash=password_hash,
            must_change_password=True,
            status="active",
            failed_login_count=0,
            locked_until=None,
            created_at=now,
            updated_at=now,
        )
        self._accounts[account.id] = account
        self._idempotency[key] = (fingerprint, account.id)
        return account, False

    def list_household(self, household_id: UUID) -> list[AccountRecord]:
        return sorted(
            (item for item in self._accounts.values() if item.household_id == household_id),
            key=lambda item: (item.created_at, item.id),
        )

    def list_parent_accounts(self) -> list[AccountRecord]:
        return sorted(
            (item for item in self._accounts.values() if item.role is AccountRole.PARENT),
            key=lambda item: (item.created_at, item.id),
        )

    def delete_child_account(self, household_id: UUID, child_id: UUID) -> None:
        account_ids = [
            account.id
            for account in self.list_household(household_id)
            if account.role is AccountRole.CHILD and account.child_id == child_id
        ]
        for account_id in account_ids:
            self.revoke_account_sessions(account_id, self._now())
            self._accounts.pop(account_id, None)
        self._idempotency = {
            key: value for key, value in self._idempotency.items() if value[1] not in account_ids
        }

    def delete_parent_account(self, account_id: UUID) -> None:
        account = self.get(account_id)
        if account.role is not AccountRole.PARENT:
            raise LookupError
        self.revoke_account_sessions(account_id, self._now())
        del self._accounts[account_id]
        self._idempotency = {
            key: value for key, value in self._idempotency.items() if value[1] != account_id
        }

    def set_login_failure(self, account_id: UUID, now: datetime) -> None:
        account = self.get(account_id)
        count = account.failed_login_count + 1
        locked_until = now + LOCKOUT_FOR if count >= LOCKOUT_AFTER_FAILURES else None
        self._accounts[account_id] = account.__class__(
            **{
                **account.__dict__,
                "failed_login_count": count,
                "locked_until": locked_until,
                "updated_at": now,
            }
        )

    def clear_login_failures(self, account_id: UUID) -> None:
        account = self.get(account_id)
        self._accounts[account_id] = account.__class__(
            **{
                **account.__dict__,
                "failed_login_count": 0,
                "locked_until": None,
                "updated_at": self._now(),
            }
        )

    def set_password(
        self, account_id: UUID, password_hash: str, must_change_password: bool
    ) -> AccountRecord:
        account = self.get(account_id)
        updated = account.__class__(
            **{
                **account.__dict__,
                "password_hash": password_hash,
                "must_change_password": must_change_password,
                "failed_login_count": 0,
                "locked_until": None,
                "updated_at": self._now(),
            }
        )
        self._accounts[account_id] = updated
        return updated

    def set_status(self, account_id: UUID, enabled: bool) -> AccountRecord:
        account = self.get(account_id)
        updated = account.__class__(
            **{
                **account.__dict__,
                "status": "active" if enabled else "disabled",
                "updated_at": self._now(),
            }
        )
        self._accounts[account_id] = updated
        return updated

    def create_session(
        self, account: AccountRecord, token_digest: str, created_at: datetime, expires_at: datetime
    ) -> SessionRecord:
        session = SessionRecord(
            uuid4(), account.id, account.household_id, token_digest, created_at, expires_at, None
        )
        self._sessions[session.id] = session
        return session

    def get_session(self, token_digest: str) -> SessionRecord | None:
        return next(
            (item for item in self._sessions.values() if item.token_digest == token_digest), None
        )

    def revoke_session(self, session_id: UUID, now: datetime) -> None:
        session = self._sessions.get(session_id)
        if session is not None and session.revoked_at is None:
            self._sessions[session_id] = session.__class__(
                **{**session.__dict__, "revoked_at": now}
            )

    def revoke_account_sessions(self, account_id: UUID, now: datetime) -> None:
        for session in tuple(self._sessions.values()):
            if session.account_id == account_id and session.revoked_at is None:
                self.revoke_session(session.id, now)

    @property
    def audit_events(self) -> list[AuditEvent]:
        return list(self._audit_events)

    def record_audit_event(
        self, household_id: UUID, event_name: str, resource_id: UUID, recorded_at: datetime
    ) -> AuditEvent:
        event = AuditEvent(
            id=uuid4(),
            household_id=household_id,
            event_name=event_name,
            resource_id=resource_id,
            recorded_at=recorded_at,
        )
        self._audit_events.append(event)
        return event


class PostgresAccountRepository:
    def __init__(self, url: str | None = None) -> None:
        self._engine = create_engine(url or database_url(), pool_pre_ping=True)
        metadata = MetaData()
        self._accounts = Table("accounts", metadata, autoload_with=self._engine)
        self._sessions = Table("auth_sessions", metadata, autoload_with=self._engine)
        self._idempotency = Table("idempotency_records", metadata, autoload_with=self._engine)
        self._audits = Table("audit_events", metadata, autoload_with=self._engine)

    @property
    def engine(self) -> Engine:
        return self._engine

    def close(self) -> None:
        self._engine.dispose()

    @staticmethod
    def _account(row: RowMapping) -> AccountRecord:
        payload = dict(row)
        payload["role"] = AccountRole(payload["role"])
        return AccountRecord(**payload)

    @staticmethod
    def _session(row: RowMapping) -> SessionRecord:
        return SessionRecord(**dict(row))

    def ensure_bootstrap(self, household_id: UUID = DEFAULT_HOUSEHOLD_ID) -> AccountRecord:
        with self._engine.begin() as connection:
            connection.exec_driver_sql("SELECT pg_advisory_xact_lock(7150017)")
            row = connection.execute(select(self._accounts).limit(1)).mappings().one_or_none()
            if row is not None:
                return self._account(row)
            now = datetime.now(UTC)
            account = AccountRecord(
                uuid4(),
                household_id,
                BOOTSTRAP_USERNAME,
                AccountRole.SUPER_ADMIN,
                None,
                hash_bootstrap_password(),
                True,
                "active",
                0,
                None,
                now,
                now,
            )
            connection.execute(insert(self._accounts).values(**account.__dict__))
            return account

    def get_by_username(self, username: str) -> AccountRecord | None:
        normalized = normalize_username(username)
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    select(self._accounts).where(self._accounts.c.username == normalized)
                )
                .mappings()
                .one_or_none()
            )
        return self._account(row) if row is not None else None

    def get(self, account_id: UUID) -> AccountRecord:
        with self._engine.connect() as connection:
            row = (
                connection.execute(select(self._accounts).where(self._accounts.c.id == account_id))
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise LookupError
        return self._account(row)

    def create_child(
        self,
        household_id: UUID,
        username: str,
        password_hash: str,
        child_id: UUID,
        idempotency_key: str,
        fingerprint: str,
    ) -> tuple[AccountRecord, bool]:
        normalized = normalize_username(username)
        now = datetime.now(UTC)
        account = AccountRecord(
            uuid4(),
            household_id,
            normalized,
            AccountRole.CHILD,
            child_id,
            password_hash,
            True,
            "active",
            0,
            None,
            now,
            now,
        )
        try:
            with self._engine.begin() as connection:
                existing = (
                    connection.execute(
                        select(self._idempotency).where(
                            self._idempotency.c.household_id == household_id,
                            self._idempotency.c.operation == f"create_child_account:{household_id}",
                            self._idempotency.c.idempotency_key == idempotency_key,
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if existing is not None:
                    if existing["fingerprint"] != fingerprint:
                        raise IdempotencyConflictError
                    row = (
                        connection.execute(
                            select(self._accounts).where(
                                self._accounts.c.id == existing["resource_id"]
                            )
                        )
                        .mappings()
                        .one()
                    )
                    return self._account(row), True
                connection.execute(insert(self._accounts).values(**account.__dict__))
                connection.execute(
                    insert(self._idempotency).values(
                        household_id=household_id,
                        operation=f"create_child_account:{household_id}",
                        idempotency_key=idempotency_key,
                        fingerprint=fingerprint,
                        resource_type="account",
                        resource_id=account.id,
                        created_at=now,
                    )
                )
        except IntegrityError as error:
            diagnostic = getattr(error.orig, "diag", None)
            if getattr(diagnostic, "constraint_name", None) in {
                "uq_accounts_username",
                "uq_accounts_household_username",
            }:
                raise DuplicateUsernameError("username already exists") from error
            raise
        return account, False

    def create_parent(
        self,
        household_id: UUID,
        username: str,
        password_hash: str,
        role: AccountRole,
        idempotency_key: str,
        fingerprint: str,
    ) -> tuple[AccountRecord, bool]:
        if role not in {AccountRole.PARENT, AccountRole.SUPER_ADMIN}:
            raise ValueError("parent account role is required")
        normalized = normalize_username(username)
        now = datetime.now(UTC)
        account = AccountRecord(
            uuid4(),
            household_id,
            normalized,
            role,
            None,
            password_hash,
            True,
            "active",
            0,
            None,
            now,
            now,
        )
        operation = f"create_parent_account:{household_id}"
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
                    row = (
                        connection.execute(
                            select(self._accounts).where(
                                self._accounts.c.id == existing["resource_id"]
                            )
                        )
                        .mappings()
                        .one()
                    )
                    return self._account(row), True
                connection.execute(insert(self._accounts).values(**account.__dict__))
                connection.execute(
                    insert(self._idempotency).values(
                        household_id=household_id,
                        operation=operation,
                        idempotency_key=idempotency_key,
                        fingerprint=fingerprint,
                        resource_type="account",
                        resource_id=account.id,
                        created_at=now,
                    )
                )
        except IntegrityError as error:
            diagnostic = getattr(error.orig, "diag", None)
            if getattr(diagnostic, "constraint_name", None) in {
                "uq_accounts_username",
                "uq_accounts_household_username",
            }:
                raise DuplicateUsernameError("username already exists") from error
            raise
        return account, False

    def list_household(self, household_id: UUID) -> list[AccountRecord]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                select(self._accounts)
                .where(self._accounts.c.household_id == household_id)
                .order_by(self._accounts.c.created_at, self._accounts.c.id)
            ).mappings()
            return [self._account(row) for row in rows]

    def list_parent_accounts(self) -> list[AccountRecord]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                select(self._accounts)
                .where(self._accounts.c.role == AccountRole.PARENT.value)
                .order_by(self._accounts.c.created_at, self._accounts.c.id)
            ).mappings()
            return [self._account(row) for row in rows]

    def delete_child_account(self, household_id: UUID, child_id: UUID) -> None:
        with self._engine.begin() as connection:
            account_ids = connection.scalars(
                select(self._accounts.c.id).where(
                    self._accounts.c.household_id == household_id,
                    self._accounts.c.child_id == child_id,
                    self._accounts.c.role == AccountRole.CHILD.value,
                )
            ).all()
            if not account_ids:
                return
            connection.execute(
                delete(self._sessions).where(self._sessions.c.account_id.in_(account_ids))
            )
            connection.execute(
                delete(self._idempotency).where(self._idempotency.c.resource_id.in_(account_ids))
            )
            connection.execute(delete(self._accounts).where(self._accounts.c.id.in_(account_ids)))

    def delete_parent_account(self, account_id: UUID) -> None:
        try:
            with self._engine.begin() as connection:
                account = (
                    connection.execute(
                        select(self._accounts).where(self._accounts.c.id == account_id)
                    )
                    .mappings()
                    .one_or_none()
                )
                if account is None or account["role"] != AccountRole.PARENT.value:
                    raise LookupError
                connection.execute(
                    delete(self._sessions).where(self._sessions.c.account_id == account_id)
                )
                connection.execute(
                    delete(self._idempotency).where(self._idempotency.c.resource_id == account_id)
                )
                connection.execute(delete(self._accounts).where(self._accounts.c.id == account_id))
        except IntegrityError as error:
            diagnostic = getattr(error.orig, "diag", None)
            if getattr(diagnostic, "constraint_name", None) == "fk_child_profiles_owner_account":
                raise ValueError("parent still owns children") from error
            raise

    def set_login_failure(self, account_id: UUID, now: datetime) -> None:
        account = self.get(account_id)
        count = account.failed_login_count + 1
        locked_until = now + LOCKOUT_FOR if count >= LOCKOUT_AFTER_FAILURES else None
        with self._engine.begin() as connection:
            connection.execute(
                update(self._accounts)
                .where(self._accounts.c.id == account_id)
                .values(failed_login_count=count, locked_until=locked_until, updated_at=now)
            )

    def clear_login_failures(self, account_id: UUID) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                update(self._accounts)
                .where(self._accounts.c.id == account_id)
                .values(failed_login_count=0, locked_until=None, updated_at=datetime.now(UTC))
            )

    def set_password(
        self, account_id: UUID, password_hash: str, must_change_password: bool
    ) -> AccountRecord:
        with self._engine.begin() as connection:
            connection.execute(
                update(self._accounts)
                .where(self._accounts.c.id == account_id)
                .values(
                    password_hash=password_hash,
                    must_change_password=must_change_password,
                    failed_login_count=0,
                    locked_until=None,
                    updated_at=datetime.now(UTC),
                )
            )
        return self.get(account_id)

    def set_status(self, account_id: UUID, enabled: bool) -> AccountRecord:
        with self._engine.begin() as connection:
            connection.execute(
                update(self._accounts)
                .where(self._accounts.c.id == account_id)
                .values(status="active" if enabled else "disabled", updated_at=datetime.now(UTC))
            )
        return self.get(account_id)

    def create_session(
        self, account: AccountRecord, token_digest: str, created_at: datetime, expires_at: datetime
    ) -> SessionRecord:
        session = SessionRecord(
            uuid4(), account.id, account.household_id, token_digest, created_at, expires_at, None
        )
        with self._engine.begin() as connection:
            connection.execute(insert(self._sessions).values(**session.__dict__))
        return session

    def get_session(self, token_digest: str) -> SessionRecord | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    select(self._sessions).where(self._sessions.c.token_digest == token_digest)
                )
                .mappings()
                .one_or_none()
            )
        return self._session(row) if row is not None else None

    def revoke_session(self, session_id: UUID, now: datetime) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                update(self._sessions)
                .where(self._sessions.c.id == session_id, self._sessions.c.revoked_at.is_(None))
                .values(revoked_at=now)
            )

    def revoke_account_sessions(self, account_id: UUID, now: datetime) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                update(self._sessions)
                .where(
                    self._sessions.c.account_id == account_id, self._sessions.c.revoked_at.is_(None)
                )
                .values(revoked_at=now)
            )

    def record_audit_event(
        self, household_id: UUID, event_name: str, resource_id: UUID, recorded_at: datetime
    ) -> AuditEvent:
        event = AuditEvent(
            id=uuid4(),
            household_id=household_id,
            event_name=event_name,
            resource_id=resource_id,
            recorded_at=recorded_at,
        )
        with self._engine.begin() as connection:
            connection.execute(insert(self._audits).values(**event.model_dump()))
        return event


class AuthService:
    def __init__(
        self, repository: AccountRepository, *, household_id: UUID = DEFAULT_HOUSEHOLD_ID
    ) -> None:
        self._repository = repository
        self._household_id = household_id

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _digest(token: str) -> str:
        return sha256(token.encode("ascii")).hexdigest()

    def _audit(self, household_id: UUID, event_name: str, resource_id: UUID, now: datetime) -> None:
        """Persist only stable authentication metadata, never credentials or tokens."""

        self._repository.record_audit_event(household_id, event_name, resource_id, now)

    def login(self, request: LoginRequest, *, remote_host: str | None) -> LoginResponse:
        try:
            account = self._repository.get_by_username(request.username)
        except (PasswordPolicyError, LookupError):
            account = None
        now = self._now()
        if account is None:
            self._audit(self._household_id, "auth_login_failed", ANONYMOUS_RESOURCE_ID, now)
            raise AuthError
        if account.status != "active":
            self._audit(account.household_id, "auth_login_blocked", account.id, now)
            raise AuthError
        if account.locked_until is not None and account.locked_until > now:
            self._audit(account.household_id, "auth_login_blocked", account.id, now)
            raise AuthError
        if not verify_password(account.password_hash, request.password):
            self._repository.set_login_failure(account.id, now)
            self._audit(account.household_id, "auth_login_failed", account.id, now)
            if account.failed_login_count + 1 >= LOCKOUT_AFTER_FAILURES:
                self._audit(account.household_id, "auth_account_locked", account.id, now)
            raise AuthError
        self._repository.clear_login_failures(account.id)
        token = secrets.token_urlsafe(32)
        session = self._repository.create_session(
            account, self._digest(token), now, now + SESSION_TTL
        )
        self._audit(account.household_id, "auth_login_succeeded", account.id, now)
        return LoginResponse(
            account=_view(account), access_token=token, expires_at=session.expires_at
        )

    def authenticate(self, token: str) -> tuple[AccountRecord, SessionRecord]:
        if not token or len(token) > 512:
            raise AuthError
        session = self._repository.get_session(self._digest(token))
        if session is None or session.revoked_at is not None or session.expires_at <= self._now():
            raise AuthError
        account = self._repository.get(session.account_id)
        if account.status != "active":
            raise AuthError
        return account, session

    def change_password(
        self, account: AccountRecord, current_password: str, new_password: str
    ) -> LoginResponse:
        if not verify_password(account.password_hash, current_password):
            self._audit(
                account.household_id,
                "auth_password_change_failed",
                account.id,
                self._now(),
            )
            raise AuthError
        password_hash = hash_password(new_password, role=account.role)
        updated = self._repository.set_password(account.id, password_hash, False)
        now = self._now()
        self._repository.revoke_account_sessions(account.id, now)
        token = secrets.token_urlsafe(32)
        session = self._repository.create_session(
            updated, self._digest(token), now, now + SESSION_TTL
        )
        self._audit(account.household_id, "auth_password_changed", account.id, now)
        return LoginResponse(
            account=_view(updated), access_token=token, expires_at=session.expires_at
        )

    def logout(self, session: SessionRecord) -> None:
        now = self._now()
        self._repository.revoke_session(session.id, now)
        self._audit(session.household_id, "auth_logout", session.account_id, now)

    def create_child_account(
        self, household_id: UUID, request: CreateChildAccountRequest, idempotency_key: str
    ) -> tuple[AccountView, bool]:
        fingerprint = sha256(request.model_dump_json().encode()).hexdigest()
        account, replayed = self._repository.create_child(
            household_id,
            normalize_username(request.username),
            hash_password(request.password, role=AccountRole.CHILD),
            request.child_id,
            idempotency_key,
            fingerprint,
        )
        if not replayed:
            self._audit(household_id, "auth_child_account_created", account.id, self._now())
        return _view(account), replayed

    def create_parent_account(
        self,
        household_id: UUID,
        request: CreateParentAccountRequest,
        idempotency_key: str,
    ) -> tuple[AccountView, bool]:
        role = AccountRole.PARENT
        fingerprint = sha256(request.model_dump_json().encode()).hexdigest()
        account, replayed = self._repository.create_parent(
            household_id,
            normalize_username(request.username),
            hash_password(request.password, role=role),
            role,
            idempotency_key,
            fingerprint,
        )
        if not replayed:
            self._audit(household_id, "auth_parent_account_created", account.id, self._now())
        return _view(account), replayed

    def provision_household(
        self, request: CreateHouseholdRequest, idempotency_key: str
    ) -> tuple[AccountView, bool]:
        # A retry must reopen the same isolated Household rather than silently
        # creating another family. The key is client generated and only accepted
        # from an already authenticated administrator.
        household_id = uuid5(NAMESPACE_URL, f"study-household:{idempotency_key}")
        account, replayed = self.create_parent_account(
            household_id,
            CreateParentAccountRequest(
                username=request.parent_username, password=request.parent_password
            ),
            idempotency_key,
        )
        return account, replayed

    def list_family_parents(
        self, profile_repository: ProfileRepository
    ) -> list[FamilyParentView]:
        return [
            FamilyParentView(
                account=_view(account),
                child_count=len(
                    profile_repository.list_children(
                        account.household_id, owner_account_id=account.id
                    )
                ),
            )
            for account in self._repository.list_parent_accounts()
        ]

    def delete_parent_account(self, account_id: UUID) -> None:
        account = self._repository.get(account_id)
        if account.role is not AccountRole.PARENT:
            raise LookupError
        self._repository.delete_parent_account(account_id)
        self._audit(account.household_id, "auth_parent_account_deleted", account_id, self._now())

    def reset_password(self, account_id: UUID, new_password: str) -> AccountView:
        account = self._repository.get(account_id)
        updated = self._repository.set_password(
            account_id, hash_password(new_password, role=account.role), True
        )
        now = self._now()
        self._repository.revoke_account_sessions(account_id, now)
        self._audit(account.household_id, "auth_password_reset", account_id, now)
        return _view(updated)

    def verify_current_password(self, account_id: UUID, current_password: str) -> None:
        account = self._repository.get(account_id)
        if not verify_password(account.password_hash, current_password):
            self._audit(
                account.household_id,
                "auth_reauthentication_failed",
                account.id,
                self._now(),
            )
            raise AuthError

    def set_status(self, account_id: UUID, enabled: bool) -> AccountView:
        account = self._repository.get(account_id)
        updated = self._repository.set_status(account_id, enabled)
        now = self._now()
        if not enabled:
            self._repository.revoke_account_sessions(account_id, now)
        self._audit(
            account.household_id,
            "auth_account_enabled" if enabled else "auth_account_disabled",
            account_id,
            now,
        )
        return _view(updated)

    def view(self, account: AccountRecord) -> AccountView:
        return _view(account)
