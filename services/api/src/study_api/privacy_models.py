"""Provider-neutral privacy and question-analysis contracts.

These models describe the new ADR-0015 boundary without selecting a cloud
Provider or persisting a job.  Raw image bytes, object keys, OCR text used for
detection, and Provider payloads deliberately do not appear in the contracts.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from study_api.domain.models import AnswerState

AnswerStep = Annotated[str, Field(min_length=1, max_length=500)]


def _no_control_characters(value: str | None) -> str | None:
    if value is None:
        return None
    if any(ord(character) < 0x20 and character not in "\n\t" for character in value):
        raise ValueError("text cannot contain control characters")
    return value


class SensitiveRegionKind(StrEnum):
    NAME = "name"
    SCHOOL = "school"
    CLASS = "class"
    GRADE = "grade"
    STUDENT_ID = "student_id"
    EXAM_ID = "exam_id"
    SEAT_NUMBER = "seat_number"
    PHONE = "phone"
    ADDRESS = "address"
    SIGNATURE = "signature"
    FACE = "face"
    QR_CODE = "qr_code"
    BARCODE = "barcode"


class PrivacySanitization(BaseModel):
    """Safe metadata for one generated derivative, never the derivative bytes."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["privacy-sanitization.v1"] = "privacy-sanitization.v1"
    sanitizer_version: str = Field(min_length=1, max_length=64)
    safe_to_upload: bool
    requires_confirmation: Literal[True] = True
    sensitive_types: tuple[SensitiveRegionKind, ...] = Field(max_length=32)
    region_count: int = Field(ge=0, le=256)
    face_detected: bool
    qr_detected: bool
    barcode_detected: bool
    blocked_reasons: tuple[str, ...] = Field(max_length=16)
    sanitized_derivative_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("sanitizer_version", "blocked_reasons", mode="before")
    @classmethod
    def validate_text_fields(cls, value: object) -> object:
        if isinstance(value, str):
            return _no_control_characters(value)
        if isinstance(value, (tuple, list)):
            return tuple(_no_control_characters(str(item)) for item in value)
        return value


class ImageAnalysisJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"


class StartImageAnalysisRequest(BaseModel):
    """User-confirmed sanitization receipt bound to the uploaded derivative."""

    model_config = ConfigDict(frozen=True)

    expected_capture_version: int = Field(ge=1)
    sanitization: PrivacySanitization
    user_confirmed: Literal[True] = True


class ImageAnalysisJobReceipt(BaseModel):
    """Provider-neutral job state; no URL, object key, or raw image field."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    capture_id: UUID
    household_id: UUID
    child_id: UUID
    status: ImageAnalysisJobStatus
    attempt: int = Field(ge=0)
    sanitization_schema_version: Literal["privacy-sanitization.v1"]
    sanitized_derivative_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: datetime
    updated_at: datetime
    extraction_id: UUID | None = None
    error_code: str | None = Field(default=None, min_length=1, max_length=64)


class QuestionExtraction(BaseModel):
    """Human-confirmable structure returned by a future visual Provider."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["question-extraction.v1"] = "question-extraction.v1"
    subject: Literal["math"]
    question_text: str = Field(min_length=1, max_length=4000)
    options: tuple[str, ...] = Field(max_length=20)
    formulas: tuple[str, ...] = Field(max_length=50)
    has_diagram: bool
    has_handwriting: bool
    detected_answer: str | None = Field(default=None, max_length=1000)
    answer_state: AnswerState = AnswerState.UNCLEAR
    answer_state_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    answer_steps: tuple[AnswerStep, ...] = Field(default=(), max_length=30)
    question_region_count: int = Field(ge=0, le=256)
    confidence: float = Field(ge=0.0, le=1.0)
    needs_confirmation: Literal[True] = True

    _question_text_has_no_controls = field_validator("question_text", "detected_answer")(
        _no_control_characters
    )
    _options_have_no_controls = field_validator("options", "formulas", "answer_steps")(
        lambda values: tuple(_no_control_characters(value) for value in values)
    )


class QuestionExtractionRecord(BaseModel):
    """Persisted, still-unverified Provider extraction for human review."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    capture_id: UUID
    household_id: UUID
    child_id: UUID
    extraction: QuestionExtraction
    created_at: datetime


class VerifyQuestionRequest(BaseModel):
    """User-edited fields that turn one extraction into a Tutor-safe fact."""

    model_config = ConfigDict(frozen=True)

    expected_capture_version: int = Field(ge=1)
    question_text: str = Field(min_length=1, max_length=4000)
    options: tuple[str, ...] = Field(default=(), max_length=20)
    formulas: tuple[str, ...] = Field(default=(), max_length=50)
    has_diagram: bool = False
    has_handwriting: bool = False
    answer_text: str | None = Field(default=None, max_length=1000)
    answer_state: AnswerState = AnswerState.UNCLEAR
    answer_state_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    answer_steps: tuple[AnswerStep, ...] = Field(default=(), max_length=30)
    evidence_confirmed: bool = False

    _question_text_has_no_controls = field_validator("question_text", "answer_text")(
        _no_control_characters
    )
    _options_have_no_controls = field_validator("options", "formulas", "answer_steps")(
        lambda values: tuple(_no_control_characters(value) for value in values)
    )


class VerifiedQuestion(BaseModel):
    """Business input for Tutor only after explicit human confirmation."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    capture_id: UUID
    extraction_id: UUID
    version: int = Field(ge=1)
    subject: Literal["math"]
    question_text: str = Field(min_length=1, max_length=4000)
    options: tuple[str, ...] = Field(max_length=20)
    formulas: tuple[str, ...] = Field(max_length=50)
    has_diagram: bool
    has_handwriting: bool
    answer_text: str | None = Field(default=None, max_length=1000)
    answer_state: AnswerState = AnswerState.UNCLEAR
    answer_state_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    answer_steps: tuple[AnswerStep, ...] = Field(default=(), max_length=30)
    evidence_confirmed: bool = False
    verified_by: Literal["child", "parent"]
    verified_at: datetime

    _question_text_has_no_controls = field_validator("question_text", "answer_text")(
        _no_control_characters
    )
    _options_have_no_controls = field_validator("options", "formulas", "answer_steps")(
        lambda values: tuple(_no_control_characters(value) for value in values)
    )
