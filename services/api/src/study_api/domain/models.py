"""Synthetic household profile domain models for the first vertical slice."""

from datetime import date, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DemoRole(StrEnum):
    """Roles supported by the local-only synthetic principal adapter."""

    PARENT = "parent"
    CHILD = "child"


class Subject(StrEnum):
    MATH = "math"


class DeviceKind(StrEnum):
    CHILD = "child"
    PARENT = "parent"


class DevicePlatform(StrEnum):
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"


class TaskStatus(StrEnum):
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"


class StudySessionStatus(StrEnum):
    ACTIVE = "active"


class CaptureStatus(StrEnum):
    NEEDS_CORRECTION = "needs_correction"
    CORRECTED = "corrected"


class SyncEventKind(StrEnum):
    RECORD_ATTEMPT = "record_attempt"


class ChildProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    household_id: UUID
    display_name: str
    grade: int = Field(ge=1, le=6)
    curriculum_version: str
    subjects: list[Subject]
    created_at: datetime


class CreateChildRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    grade: int = Field(ge=1, le=6)
    curriculum_version: str = Field(min_length=1, max_length=80)
    subjects: list[Subject] = Field(min_length=1)


class Device(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    household_id: UUID
    kind: DeviceKind
    platform: DevicePlatform
    display_name: str
    status: Literal["active"] = "active"
    registered_at: datetime


class CreateDeviceRequest(BaseModel):
    kind: DeviceKind
    platform: DevicePlatform
    display_name: str = Field(min_length=1, max_length=80)


class StudyTask(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    household_id: UUID
    child_id: UUID
    title: str
    subject: Subject
    scheduled_for: date
    status: TaskStatus
    version: int = Field(ge=1)
    created_at: datetime


class CreateTaskRequest(BaseModel):
    child_id: UUID
    title: str = Field(min_length=1, max_length=120)
    subject: Subject
    scheduled_for: date


class StudySession(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    household_id: UUID
    child_id: UUID
    task_id: UUID
    task_version: int = Field(ge=1)
    status: StudySessionStatus
    started_at: datetime


class StartStudySessionRequest(BaseModel):
    expected_task_version: int = Field(ge=1)


class Capture(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    household_id: UUID
    child_id: UUID
    session_id: UUID
    media_type: Literal["image/jpeg", "image/png"]
    byte_size: int = Field(ge=1, le=8_000_000)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: CaptureStatus
    version: int = Field(ge=1)
    created_at: datetime


class CreateCaptureRequest(BaseModel):
    media_type: Literal["image/jpeg", "image/png"]
    byte_size: int = Field(ge=1, le=8_000_000)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class CaptureCorrection(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    capture_id: UUID
    household_id: UUID
    child_id: UUID
    sequence: int = Field(ge=1)
    corrected_text: str = Field(min_length=1, max_length=1000)
    created_at: datetime


class CorrectCaptureRequest(BaseModel):
    expected_capture_version: int = Field(ge=1)
    corrected_text: str = Field(min_length=1, max_length=1000)


class Attempt(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    event_id: UUID
    household_id: UUID
    child_id: UUID
    session_id: UUID
    sequence: int = Field(ge=1)
    answer_summary: str = Field(min_length=1, max_length=200)
    recorded_at: datetime


class RecordAttemptRequest(BaseModel):
    event_id: UUID
    answer_summary: str = Field(min_length=1, max_length=200)


class SyncEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: UUID
    idempotency_key: str = Field(min_length=8, max_length=128)
    kind: Literal[SyncEventKind.RECORD_ATTEMPT]
    session_id: UUID
    answer_summary: str = Field(min_length=1, max_length=200)


class SyncBatchRequest(BaseModel):
    schema_version: Literal[1]
    events: list[SyncEvent] = Field(min_length=1, max_length=50)


class SyncEventResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: UUID
    status: Literal["applied", "replayed"]
    attempt: Attempt


class SyncBatchResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    results: list[SyncEventResult]


class AuditEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    household_id: UUID
    event_name: str
    resource_id: UUID
    recorded_at: datetime
