"""Household profile and learning domain models."""

from datetime import date, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AccountRole(StrEnum):
    """Roles supported by Household password accounts."""

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
    COMPLETED = "completed"
    SKIPPED = "skipped"


class TaskSourceType(StrEnum):
    MANUAL = "manual"
    MISTAKE_REVIEW = "mistake_review"
    CURRICULUM_EXERCISE = "curriculum_exercise"
    MIXED_PLAN = "mixed_plan"


class StudySessionStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"


class SessionOutcome(StrEnum):
    LEARNED = "learned"
    NEEDS_REVIEW = "needs_review"
    SKIPPED = "skipped"


class AnswerState(StrEnum):
    """The four explicit answer-area states returned by capture review."""

    WORKED = "worked"
    BLANK = "blank"
    UNCLEAR = "unclear"
    ANSWER_AREA_MISSING = "answer_area_missing"


class CaptureStatus(StrEnum):
    UPLOAD_PENDING = "upload_pending"
    NEEDS_CORRECTION = "needs_correction"
    CORRECTED = "corrected"


class OcrResultStatus(StrEnum):
    CANDIDATE = "candidate"
    EMPTY = "empty"


class OcrJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class OcrMode(StrEnum):
    TEXT = "text"
    FORMULA = "formula"


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


class UpdateChildRequest(CreateChildRequest):
    """Replace the editable fields of one ChildProfile."""


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


class TaskExercise(BaseModel):
    """One source-backed question delivered as part of a task."""

    model_config = ConfigDict(frozen=True)

    question_text: str = Field(min_length=1, max_length=4000)
    source_type: Literal["mistake", "curriculum"]
    mistake_id: UUID | None = None
    snapshot_id: UUID | None = None
    curriculum_chunk_id: UUID | None = None
    knowledge_point_id: UUID | None = None
    knowledge_key: str | None = Field(default=None, max_length=80)
    source_title: str | None = Field(default=None, max_length=160)
    source_page: int | None = Field(default=None, ge=1)
    visual_description: str | None = Field(default=None, max_length=1000)
    requires_visual_context: bool = False


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
    source_type: TaskSourceType = TaskSourceType.MANUAL
    reason: str | None = Field(default=None, max_length=500)
    knowledge_point: str | None = Field(default=None, max_length=120)
    knowledge_point_id: UUID | None = None
    exercises: tuple[TaskExercise, ...] = Field(default=(), max_length=5)
    estimated_minutes: int | None = Field(default=None, ge=1, le=120)


class CreateTaskRequest(BaseModel):
    child_id: UUID
    title: str = Field(min_length=1, max_length=120)
    subject: Subject
    scheduled_for: date
    source_type: TaskSourceType = TaskSourceType.MANUAL
    reason: str | None = Field(default=None, max_length=500)
    knowledge_point: str | None = Field(default=None, max_length=120)
    knowledge_point_id: UUID | None = None
    exercises: tuple[TaskExercise, ...] = Field(default=(), max_length=5)
    estimated_minutes: int | None = Field(default=None, ge=1, le=120)


class StudySession(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    household_id: UUID
    child_id: UUID
    task_id: UUID
    task_version: int = Field(ge=1)
    status: StudySessionStatus
    started_at: datetime
    completed_at: datetime | None = None
    outcome: SessionOutcome | None = None


class StartStudySessionRequest(BaseModel):
    expected_task_version: int = Field(ge=1)


class CompleteStudySessionRequest(BaseModel):
    outcome: SessionOutcome


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


class CaptureUpload(BaseModel):
    """Short-lived upload capability; no separate object-key field is exposed."""

    model_config = ConfigDict(frozen=True)

    capture: Capture
    upload_url: str
    upload_expires_at: datetime


class ConfirmCaptureUploadRequest(BaseModel):
    expected_capture_version: int = Field(ge=1)


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


class ConfirmOcrCandidateRequest(BaseModel):
    expected_capture_version: int = Field(ge=1)
    candidate_id: UUID


class EnqueueOcrJobRequest(BaseModel):
    mode: OcrMode = OcrMode.TEXT


class OcrResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    capture_id: UUID
    household_id: UUID
    child_id: UUID
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    model_version: str = Field(min_length=1, max_length=80)
    schema_version: str = Field(min_length=1, max_length=32)
    confidence: float = Field(ge=0.0, le=1.0)
    status: OcrResultStatus
    requires_manual_confirmation: Literal[True] = True
    created_at: datetime


class OcrCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    result_id: UUID
    sequence: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=1000)
    confidence: float = Field(ge=0.0, le=1.0)


class OcrResultWithCandidates(BaseModel):
    model_config = ConfigDict(frozen=True)

    result: OcrResult
    candidates: list[OcrCandidate]


class OcrJobReceipt(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    capture_id: UUID
    mode: OcrMode
    status: OcrJobStatus
    attempt: int = Field(ge=0)
    enqueued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result_id: UUID | None = None


class Attempt(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    event_id: UUID
    household_id: UUID
    child_id: UUID
    session_id: UUID
    sequence: int = Field(ge=1)
    answer_summary: str = Field(min_length=1, max_length=200)
    answer_state: AnswerState = AnswerState.UNCLEAR
    evidence_confirmed: bool = False
    recorded_at: datetime


class RecordAttemptRequest(BaseModel):
    event_id: UUID
    answer_summary: str = Field(min_length=1, max_length=200)
    answer_state: AnswerState = AnswerState.UNCLEAR
    evidence_confirmed: bool = False


class SyncEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: UUID
    idempotency_key: str = Field(min_length=8, max_length=128)
    kind: Literal[SyncEventKind.RECORD_ATTEMPT]
    session_id: UUID
    answer_summary: str = Field(min_length=1, max_length=200)
    answer_state: AnswerState = AnswerState.UNCLEAR
    evidence_confirmed: bool = False


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
