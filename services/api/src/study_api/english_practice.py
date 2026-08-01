"""Provider-neutral, privacy-minimized English speaking practice domain."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from threading import RLock
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Date, MetaData, Table, create_engine, func, insert, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from study_api.database import database_url
from study_api.domain.repository import IdempotencyConflictError


class EnglishLevel(StrEnum):
    PRE_A1 = "pre_a1"
    A1 = "a1"
    A2 = "a2"


class EnglishSessionStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    FAILED = "failed"


class EnglishScenario(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    description: str
    target_minutes: int = Field(ge=5, le=8)


ENGLISH_SCENARIOS = (
    EnglishScenario(
        id="greetings",
        title="打招呼",
        description="练习问候、介绍心情和礼貌告别。",
        target_minutes=5,
    ),
    EnglishScenario(
        id="school",
        title="校园交流",
        description="练习课堂用品、课程和请求帮助。",
        target_minutes=7,
    ),
    EnglishScenario(
        id="food_order",
        title="点餐",
        description="练习选择食物、数量和礼貌表达。",
        target_minutes=8,
    ),
)
SCENARIO_IDS = frozenset(item.id for item in ENGLISH_SCENARIOS)


class EnglishPracticeSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    household_id: UUID
    child_id: UUID
    enabled: bool = False
    level: EnglishLevel = EnglishLevel.PRE_A1
    consent_version: str | None = None
    version: int = Field(default=0, ge=0)
    updated_by: UUID | None = None
    updated_at: datetime | None = None


class EnglishPracticeSettingsView(EnglishPracticeSettings):
    provider_available: bool
    required_consent_version: str
    daily_limit_minutes: int = 10


class UpdateEnglishPracticeSettings(BaseModel):
    enabled: bool
    level: EnglishLevel
    consent_version: str | None = Field(default=None, max_length=64)
    expected_version: int = Field(ge=0)


class StartEnglishSessionRequest(BaseModel):
    scenario_id: str = Field(min_length=1, max_length=32)


class CompleteEnglishSessionRequest(BaseModel):
    status: EnglishSessionStatus = EnglishSessionStatus.COMPLETED


class EnglishPracticeSession(BaseModel):
    """Append-only summary. Raw audio, transcript and provider messages are excluded."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    household_id: UUID
    child_id: UUID
    scenario_id: str
    level: EnglishLevel
    status: EnglishSessionStatus
    provider: str
    model_version: str
    policy_version: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: int = Field(default=0, ge=0, le=480)
    turn_count: int = Field(default=0, ge=0)
    input_audio_ms: int = Field(default=0, ge=0)
    output_audio_ms: int = Field(default=0, ge=0)
    cost_micros: int = Field(default=0, ge=0)
    feedback_tags: tuple[str, ...] = Field(default=(), max_length=3)
    failure_code: str | None = Field(default=None, max_length=64)


class EnglishPolicyDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed: bool
    reason: str
    use_chinese_fallback: bool = False


class EnglishConversationPolicy:
    """Deterministic guardrails around any future approved live provider."""

    version = "english-guided.v1"
    _personal_prompts = (
        "your name",
        "your school",
        "where do you live",
        "your address",
        "phone number",
        "email address",
        "contact you",
    )
    _unsafe_topics = (
        "adult content",
        "sexual",
        "weapon",
        "how to hurt",
        "suicide",
        "drugs",
    )

    def instruction(self, scenario_id: str, level: EnglishLevel) -> str:
        if scenario_id not in SCENARIO_IDS:
            raise LookupError
        return (
            f"Policy {self.version}. Guide only scenario={scenario_id}, level={level.value}. "
            "Use short English turns. After two consecutive communication failures, give one "
            "short Chinese hint. Never request a name, school, address, contact detail, or other "
            "personal information. Refuse adult, dangerous, and unrelated free-chat topics. "
            "Do not use search, tools, video, or external links. Keep each reply under 40 words."
        )

    def evaluate_reply(self, reply: str, *, consecutive_failures: int = 0) -> EnglishPolicyDecision:
        normalized = " ".join(reply.lower().split())
        if any(phrase in normalized for phrase in self._personal_prompts):
            return EnglishPolicyDecision(allowed=False, reason="personal_information_request")
        if any(phrase in normalized for phrase in self._unsafe_topics):
            return EnglishPolicyDecision(allowed=False, reason="unsafe_topic")
        if len(normalized.split()) > 40:
            return EnglishPolicyDecision(allowed=False, reason="reply_too_long")
        return EnglishPolicyDecision(
            allowed=True,
            reason="guided_reply",
            use_chinese_fallback=consecutive_failures >= 2,
        )


class EnglishPracticeError(RuntimeError):
    pass


class SettingsVersionConflictError(EnglishPracticeError):
    pass


class EnglishPracticeDisabledError(EnglishPracticeError):
    pass


class EnglishConsentRequiredError(EnglishPracticeError):
    pass


class EnglishSessionLimitError(EnglishPracticeError):
    pass


class EnglishActiveSessionError(EnglishPracticeError):
    pass


class EnglishSessionFinalizedError(EnglishPracticeError):
    pass


@dataclass(frozen=True)
class EnglishLiveConfig:
    enabled: bool = False
    provider: str = "disabled"
    allow_test_provider: bool = False
    consent_version: str = "english-audio-consent.v1"
    daily_limit_seconds: int = 600
    session_limit_seconds: int = 480
    idle_timeout_seconds: int = 30
    policy_version: str = "english-guided.v1"

    @classmethod
    def from_environment(cls) -> EnglishLiveConfig:
        return cls(
            enabled=_env_bool("STUDY_ENGLISH_LIVE_ENABLED", False),
            provider=os.environ.get("STUDY_ENGLISH_LIVE_PROVIDER", "disabled").strip().lower(),
            consent_version=os.environ.get(
                "STUDY_ENGLISH_LIVE_CONSENT_VERSION", "english-audio-consent.v1"
            ).strip(),
        )

    @property
    def provider_available(self) -> bool:
        return self.enabled and self.provider == "fake" and self.allow_test_provider


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    if raw.strip().lower() in {"1", "true", "yes", "on"}:
        return True
    if raw.strip().lower() in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be a boolean")


class EnglishLiveSession(Protocol):
    async def send_audio(self, pcm: bytes) -> None: ...

    async def interrupt(self) -> None: ...

    def finish_input(self) -> AsyncIterator[bytes]: ...

    async def close(self) -> None: ...


class EnglishLiveProvider(Protocol):
    name: str
    model_version: str

    @property
    def available(self) -> bool: ...

    async def open_session(
        self, *, scenario_id: str, level: EnglishLevel, policy_instruction: str
    ) -> EnglishLiveSession: ...


class _DisabledEnglishLiveSession:
    async def send_audio(self, pcm: bytes) -> None:
        del pcm
        raise EnglishPracticeDisabledError("english live provider is unavailable")

    async def interrupt(self) -> None:
        raise EnglishPracticeDisabledError("english live provider is unavailable")

    async def finish_input(self) -> AsyncIterator[bytes]:
        raise EnglishPracticeDisabledError("english live provider is unavailable")
        yield b""  # pragma: no cover -- makes this an async iterator.

    async def close(self) -> None:
        return None


class DisabledEnglishLiveProvider:
    name = "disabled"
    model_version = "none"
    available = False

    async def open_session(
        self, *, scenario_id: str, level: EnglishLevel, policy_instruction: str
    ) -> EnglishLiveSession:
        del scenario_id, level, policy_instruction
        raise EnglishPracticeDisabledError("english live provider is unavailable")


class _FakeEnglishLiveSession:
    async def send_audio(self, pcm: bytes) -> None:
        del pcm

    async def interrupt(self) -> None:
        return None

    async def finish_input(self) -> AsyncIterator[bytes]:
        # 40 ms of PCM16 little-endian mono silence at 24 kHz.
        yield bytes(1920)

    async def close(self) -> None:
        return None


class FakeEnglishLiveProvider:
    """Deterministic test provider; never selected unless explicitly allowed."""

    name = "fake"
    model_version = "fake-english-live.v1"
    available = True

    async def open_session(
        self, *, scenario_id: str, level: EnglishLevel, policy_instruction: str
    ) -> EnglishLiveSession:
        del scenario_id, level
        if not policy_instruction:
            raise ValueError("policy instruction is required")
        return _FakeEnglishLiveSession()


def build_english_provider(config: EnglishLiveConfig) -> EnglishLiveProvider:
    if config.provider_available:
        return FakeEnglishLiveProvider()
    return DisabledEnglishLiveProvider()


class EnglishPracticeRepository(Protocol):
    def get_settings(self, household_id: UUID, child_id: UUID) -> EnglishPracticeSettings: ...

    def update_settings(
        self,
        household_id: UUID,
        child_id: UUID,
        actor_id: UUID,
        request: UpdateEnglishPracticeSettings,
        idempotency_key: str,
    ) -> tuple[EnglishPracticeSettings, bool]: ...

    def start_session(
        self,
        household_id: UUID,
        child_id: UUID,
        scenario_id: str,
        config: EnglishLiveConfig,
        provider: EnglishLiveProvider,
        idempotency_key: str,
    ) -> tuple[EnglishPracticeSession, bool]: ...

    def get_session(
        self, household_id: UUID, child_id: UUID, session_id: UUID
    ) -> EnglishPracticeSession | None: ...

    def list_sessions(
        self, household_id: UUID, child_id: UUID, limit: int = 10
    ) -> tuple[EnglishPracticeSession, ...]: ...

    def record_audio(self, session_id: UUID, *, input_ms: int = 0, output_ms: int = 0) -> None: ...

    def record_turn(self, session_id: UUID) -> None: ...

    def complete_session(
        self,
        household_id: UUID,
        child_id: UUID,
        session_id: UUID,
        status: EnglishSessionStatus,
        idempotency_key: str,
        *,
        failure_code: str | None = None,
    ) -> tuple[EnglishPracticeSession, bool]: ...


class InMemoryEnglishPracticeRepository:
    def __init__(self) -> None:
        self._settings: dict[tuple[UUID, UUID], EnglishPracticeSettings] = {}
        self._sessions: dict[UUID, EnglishPracticeSession] = {}
        self._receipts: dict[tuple[UUID, str, str], tuple[str, UUID | tuple[UUID, UUID]]] = {}
        self._lock = RLock()

    def get_settings(self, household_id: UUID, child_id: UUID) -> EnglishPracticeSettings:
        return self._settings.get(
            (household_id, child_id),
            EnglishPracticeSettings(household_id=household_id, child_id=child_id),
        )

    def update_settings(
        self,
        household_id: UUID,
        child_id: UUID,
        actor_id: UUID,
        request: UpdateEnglishPracticeSettings,
        idempotency_key: str,
    ) -> tuple[EnglishPracticeSettings, bool]:
        operation = f"english_settings:{child_id}"
        fingerprint = _fingerprint(request)
        with self._lock:
            replay = self._receipt(household_id, operation, idempotency_key, fingerprint)
            if replay is not None:
                return self.get_settings(household_id, child_id), True
            current = self.get_settings(household_id, child_id)
            if request.expected_version != current.version:
                raise SettingsVersionConflictError
            settings = EnglishPracticeSettings(
                household_id=household_id,
                child_id=child_id,
                enabled=request.enabled,
                level=request.level,
                consent_version=request.consent_version,
                version=current.version + 1,
                updated_by=actor_id,
                updated_at=datetime.now(UTC),
            )
            self._settings[(household_id, child_id)] = settings
            self._receipts[(household_id, operation, idempotency_key)] = (
                fingerprint,
                (household_id, child_id),
            )
            return settings, False

    def start_session(
        self,
        household_id: UUID,
        child_id: UUID,
        scenario_id: str,
        config: EnglishLiveConfig,
        provider: EnglishLiveProvider,
        idempotency_key: str,
    ) -> tuple[EnglishPracticeSession, bool]:
        operation = f"english_session_start:{child_id}"
        fingerprint = sha256(scenario_id.encode()).hexdigest()
        with self._lock:
            replay = self._receipt(household_id, operation, idempotency_key, fingerprint)
            if isinstance(replay, UUID):
                return self._sessions[replay], True
            settings = self.get_settings(household_id, child_id)
            _check_start_gate(settings, config, provider)
            if scenario_id not in SCENARIO_IDS:
                raise LookupError
            if any(
                item.household_id == household_id
                and item.child_id == child_id
                and item.status is EnglishSessionStatus.ACTIVE
                for item in self._sessions.values()
            ):
                raise EnglishActiveSessionError
            today = datetime.now(UTC).date()
            used = sum(
                item.duration_seconds
                for item in self._sessions.values()
                if item.household_id == household_id
                and item.child_id == child_id
                and item.started_at.date() == today
            )
            if used >= config.daily_limit_seconds:
                raise EnglishSessionLimitError
            session = EnglishPracticeSession(
                id=uuid4(),
                household_id=household_id,
                child_id=child_id,
                scenario_id=scenario_id,
                level=settings.level,
                status=EnglishSessionStatus.ACTIVE,
                provider=provider.name,
                model_version=provider.model_version,
                policy_version=config.policy_version,
                started_at=datetime.now(UTC),
            )
            self._sessions[session.id] = session
            self._receipts[(household_id, operation, idempotency_key)] = (
                fingerprint,
                session.id,
            )
            return session, False

    def get_session(
        self, household_id: UUID, child_id: UUID, session_id: UUID
    ) -> EnglishPracticeSession | None:
        item = self._sessions.get(session_id)
        if item is None or item.household_id != household_id or item.child_id != child_id:
            return None
        return item

    def list_sessions(
        self, household_id: UUID, child_id: UUID, limit: int = 10
    ) -> tuple[EnglishPracticeSession, ...]:
        items = [
            item
            for item in self._sessions.values()
            if item.household_id == household_id and item.child_id == child_id
        ]
        return tuple(sorted(items, key=lambda item: item.started_at, reverse=True)[:limit])

    def record_audio(self, session_id: UUID, *, input_ms: int = 0, output_ms: int = 0) -> None:
        with self._lock:
            item = self._sessions[session_id]
            self._sessions[session_id] = item.model_copy(
                update={
                    "input_audio_ms": item.input_audio_ms + input_ms,
                    "output_audio_ms": item.output_audio_ms + output_ms,
                }
            )

    def record_turn(self, session_id: UUID) -> None:
        with self._lock:
            item = self._sessions[session_id]
            self._sessions[session_id] = item.model_copy(update={"turn_count": item.turn_count + 1})

    def complete_session(
        self,
        household_id: UUID,
        child_id: UUID,
        session_id: UUID,
        status: EnglishSessionStatus,
        idempotency_key: str,
        *,
        failure_code: str | None = None,
    ) -> tuple[EnglishPracticeSession, bool]:
        operation = f"english_session_complete:{session_id}"
        fingerprint = sha256(f"{status}:{failure_code}".encode()).hexdigest()
        with self._lock:
            replay = self._receipt(household_id, operation, idempotency_key, fingerprint)
            item = self.get_session(household_id, child_id, session_id)
            if item is None:
                raise LookupError
            if replay is not None:
                return item, True
            if item.status is not EnglishSessionStatus.ACTIVE:
                if item.status is not status:
                    raise EnglishSessionFinalizedError
                self._receipts[(household_id, operation, idempotency_key)] = (
                    fingerprint,
                    session_id,
                )
                return item, False
            now = datetime.now(UTC)
            duration = min(480, max(0, int((now - item.started_at).total_seconds())))
            completed = item.model_copy(
                update={
                    "status": status,
                    "completed_at": now,
                    "duration_seconds": duration,
                    "failure_code": failure_code,
                }
            )
            self._sessions[session_id] = completed
            self._receipts[(household_id, operation, idempotency_key)] = (
                fingerprint,
                session_id,
            )
            return completed, False

    def _receipt(
        self, household_id: UUID, operation: str, key: str, fingerprint: str
    ) -> UUID | tuple[UUID, UUID] | None:
        receipt = self._receipts.get((household_id, operation, key))
        if receipt is None:
            return None
        if receipt[0] != fingerprint:
            raise IdempotencyConflictError
        return receipt[1]


class PostgresEnglishPracticeRepository:
    def __init__(self, url: str | None = None, *, engine: Engine | None = None) -> None:
        self._owns_engine = engine is None
        self._engine = engine or create_engine(url or database_url(), pool_pre_ping=True)
        metadata = MetaData()
        self._settings = Table("english_practice_settings", metadata, autoload_with=self._engine)
        self._sessions = Table("english_practice_sessions", metadata, autoload_with=self._engine)
        self._idempotency = Table(
            "english_practice_idempotency", metadata, autoload_with=self._engine
        )

    def close(self) -> None:
        if self._owns_engine:
            self._engine.dispose()

    def get_settings(self, household_id: UUID, child_id: UUID) -> EnglishPracticeSettings:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    select(self._settings).where(
                        self._settings.c.household_id == household_id,
                        self._settings.c.child_id == child_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
        return (
            EnglishPracticeSettings.model_validate(dict(row))
            if row is not None
            else EnglishPracticeSettings(household_id=household_id, child_id=child_id)
        )

    def update_settings(
        self,
        household_id: UUID,
        child_id: UUID,
        actor_id: UUID,
        request: UpdateEnglishPracticeSettings,
        idempotency_key: str,
    ) -> tuple[EnglishPracticeSettings, bool]:
        operation = f"english_settings:{child_id}"
        fingerprint = _fingerprint(request)
        now = datetime.now(UTC)
        with self._engine.begin() as connection:
            receipt = _sql_receipt(
                connection, self._idempotency, household_id, operation, idempotency_key, fingerprint
            )
            if receipt is not None:
                row = (
                    connection.execute(
                        select(self._settings).where(
                            self._settings.c.household_id == household_id,
                            self._settings.c.child_id == child_id,
                        )
                    )
                    .mappings()
                    .one()
                )
                return EnglishPracticeSettings.model_validate(dict(row)), True
            current = (
                connection.execute(
                    select(self._settings)
                    .where(
                        self._settings.c.household_id == household_id,
                        self._settings.c.child_id == child_id,
                    )
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            version = int(current["version"]) if current is not None else 0
            if request.expected_version != version:
                raise SettingsVersionConflictError
            values = {
                "household_id": household_id,
                "child_id": child_id,
                "enabled": request.enabled,
                "level": request.level.value,
                "consent_version": request.consent_version,
                "version": version + 1,
                "updated_by": actor_id,
                "updated_at": now,
            }
            if current is None:
                connection.execute(insert(self._settings).values(**values))
            else:
                connection.execute(
                    update(self._settings)
                    .where(
                        self._settings.c.household_id == household_id,
                        self._settings.c.child_id == child_id,
                    )
                    .values(**values)
                )
            _insert_sql_receipt(
                connection,
                self._idempotency,
                household_id,
                operation,
                idempotency_key,
                fingerprint,
                child_id,
            )
        return EnglishPracticeSettings.model_validate(values), False

    def start_session(
        self,
        household_id: UUID,
        child_id: UUID,
        scenario_id: str,
        config: EnglishLiveConfig,
        provider: EnglishLiveProvider,
        idempotency_key: str,
    ) -> tuple[EnglishPracticeSession, bool]:
        operation = f"english_session_start:{child_id}"
        fingerprint = sha256(scenario_id.encode()).hexdigest()
        if scenario_id not in SCENARIO_IDS:
            raise LookupError
        with self._engine.begin() as connection:
            receipt = _sql_receipt(
                connection, self._idempotency, household_id, operation, idempotency_key, fingerprint
            )
            if receipt is not None:
                row = (
                    connection.execute(select(self._sessions).where(self._sessions.c.id == receipt))
                    .mappings()
                    .one()
                )
                return _session_from_row(row), True
            settings_row = (
                connection.execute(
                    select(self._settings)
                    .where(
                        self._settings.c.household_id == household_id,
                        self._settings.c.child_id == child_id,
                    )
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            settings = (
                EnglishPracticeSettings.model_validate(dict(settings_row))
                if settings_row is not None
                else EnglishPracticeSettings(household_id=household_id, child_id=child_id)
            )
            _check_start_gate(settings, config, provider)
            used = connection.execute(
                select(func.coalesce(func.sum(self._sessions.c.duration_seconds), 0)).where(
                    self._sessions.c.household_id == household_id,
                    self._sessions.c.child_id == child_id,
                    func.cast(func.timezone("UTC", self._sessions.c.started_at), Date)
                    == datetime.now(UTC).date(),
                )
            ).scalar_one()
            if int(used) >= config.daily_limit_seconds:
                raise EnglishSessionLimitError
            session = EnglishPracticeSession(
                id=uuid4(),
                household_id=household_id,
                child_id=child_id,
                scenario_id=scenario_id,
                level=settings.level,
                status=EnglishSessionStatus.ACTIVE,
                provider=provider.name,
                model_version=provider.model_version,
                policy_version=config.policy_version,
                started_at=datetime.now(UTC),
            )
            try:
                connection.execute(
                    insert(self._sessions).values(**session.model_dump(mode="python"))
                )
            except IntegrityError as error:
                raise EnglishActiveSessionError from error
            _insert_sql_receipt(
                connection,
                self._idempotency,
                household_id,
                operation,
                idempotency_key,
                fingerprint,
                session.id,
            )
            return session, False

    def get_session(
        self, household_id: UUID, child_id: UUID, session_id: UUID
    ) -> EnglishPracticeSession | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    select(self._sessions).where(
                        self._sessions.c.id == session_id,
                        self._sessions.c.household_id == household_id,
                        self._sessions.c.child_id == child_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
        return _session_from_row(row) if row is not None else None

    def list_sessions(
        self, household_id: UUID, child_id: UUID, limit: int = 10
    ) -> tuple[EnglishPracticeSession, ...]:
        with self._engine.connect() as connection:
            rows = (
                connection.execute(
                    select(self._sessions)
                    .where(
                        self._sessions.c.household_id == household_id,
                        self._sessions.c.child_id == child_id,
                    )
                    .order_by(self._sessions.c.started_at.desc())
                    .limit(limit)
                )
                .mappings()
                .all()
            )
        return tuple(_session_from_row(row) for row in rows)

    def record_audio(self, session_id: UUID, *, input_ms: int = 0, output_ms: int = 0) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                update(self._sessions)
                .where(
                    self._sessions.c.id == session_id,
                    self._sessions.c.status == EnglishSessionStatus.ACTIVE.value,
                )
                .values(
                    input_audio_ms=self._sessions.c.input_audio_ms + input_ms,
                    output_audio_ms=self._sessions.c.output_audio_ms + output_ms,
                )
            )

    def record_turn(self, session_id: UUID) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                update(self._sessions)
                .where(
                    self._sessions.c.id == session_id,
                    self._sessions.c.status == EnglishSessionStatus.ACTIVE.value,
                )
                .values(turn_count=self._sessions.c.turn_count + 1)
            )

    def complete_session(
        self,
        household_id: UUID,
        child_id: UUID,
        session_id: UUID,
        status: EnglishSessionStatus,
        idempotency_key: str,
        *,
        failure_code: str | None = None,
    ) -> tuple[EnglishPracticeSession, bool]:
        operation = f"english_session_complete:{session_id}"
        fingerprint = sha256(f"{status}:{failure_code}".encode()).hexdigest()
        with self._engine.begin() as connection:
            receipt = _sql_receipt(
                connection, self._idempotency, household_id, operation, idempotency_key, fingerprint
            )
            row = (
                connection.execute(
                    select(self._sessions)
                    .where(
                        self._sessions.c.id == session_id,
                        self._sessions.c.household_id == household_id,
                        self._sessions.c.child_id == child_id,
                    )
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise LookupError
            if receipt is not None:
                return _session_from_row(row), True
            item = _session_from_row(row)
            if item.status is not EnglishSessionStatus.ACTIVE:
                if item.status is not status:
                    raise EnglishSessionFinalizedError
                _insert_sql_receipt(
                    connection,
                    self._idempotency,
                    household_id,
                    operation,
                    idempotency_key,
                    fingerprint,
                    session_id,
                )
                return item, False
            now = datetime.now(UTC)
            duration = min(480, max(0, int((now - item.started_at).total_seconds())))
            connection.execute(
                update(self._sessions)
                .where(self._sessions.c.id == session_id)
                .values(
                    status=status.value,
                    completed_at=now,
                    duration_seconds=duration,
                    failure_code=failure_code,
                )
            )
            _insert_sql_receipt(
                connection,
                self._idempotency,
                household_id,
                operation,
                idempotency_key,
                fingerprint,
                session_id,
            )
            return item.model_copy(
                update={
                    "status": status,
                    "completed_at": now,
                    "duration_seconds": duration,
                    "failure_code": failure_code,
                }
            ), False


def _check_start_gate(
    settings: EnglishPracticeSettings, config: EnglishLiveConfig, provider: EnglishLiveProvider
) -> None:
    if not config.provider_available or not provider.available:
        raise EnglishPracticeDisabledError
    if not settings.enabled:
        raise EnglishPracticeDisabledError
    if settings.consent_version != config.consent_version:
        raise EnglishConsentRequiredError


def _fingerprint(model: BaseModel) -> str:
    return sha256(model.model_dump_json().encode()).hexdigest()


def _session_from_row(row) -> EnglishPracticeSession:
    payload = dict(row)
    payload["feedback_tags"] = tuple(payload.get("feedback_tags") or ())
    return EnglishPracticeSession.model_validate(payload)


def _sql_receipt(
    connection, table: Table, household_id: UUID, operation: str, key: str, fingerprint: str
) -> UUID | None:
    row = (
        connection.execute(
            select(table).where(
                table.c.household_id == household_id,
                table.c.operation == operation,
                table.c.idempotency_key == key,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    if row["fingerprint"] != fingerprint:
        raise IdempotencyConflictError
    return row["resource_id"]


def _insert_sql_receipt(
    connection,
    table: Table,
    household_id: UUID,
    operation: str,
    key: str,
    fingerprint: str,
    resource_id: UUID,
) -> None:
    connection.execute(
        insert(table).values(
            household_id=household_id,
            operation=operation,
            idempotency_key=key,
            fingerprint=fingerprint,
            resource_id=resource_id,
            created_at=datetime.now(UTC),
        )
    )
