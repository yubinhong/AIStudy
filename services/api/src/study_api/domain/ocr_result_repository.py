"""Transactional persistence for normalized, manually confirmed OCR candidates."""

from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import MetaData, Table, create_engine, insert, select
from sqlalchemy.engine import Connection, Engine, RowMapping

from study_api.database import database_url
from study_api.domain.capture_repository import CaptureStateError
from study_api.domain.learning_repository import ChildAssignmentError
from study_api.domain.models import (
    AuditEvent,
    CaptureStatus,
    OcrCandidate,
    OcrResult,
    OcrResultStatus,
)
from study_api.domain.repository import IdempotencyConflictError
from study_api.ocr_provider import OcrParseResult


def _validate_text(value: str) -> str:
    if any(ord(character) < 0x20 for character in value):
        raise ValueError("OCR text cannot contain control characters")
    return value


class OcrCandidateDraft(BaseModel):
    """Provider-neutral candidate accepted by the persistence boundary."""

    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1, max_length=1000)
    confidence: float = Field(ge=0.0, le=1.0)

    _text_has_no_controls = field_validator("text")(_validate_text)


class OcrResultDraft(BaseModel):
    """Validated OCR output; raw Provider payloads never cross this boundary."""

    model_config = ConfigDict(frozen=True)

    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    model_version: str = Field(min_length=1, max_length=80)
    schema_version: str = Field(min_length=1, max_length=32)
    confidence: float = Field(ge=0.0, le=1.0)
    status: OcrResultStatus
    requires_manual_confirmation: Literal[True] = True
    candidates: tuple[OcrCandidateDraft, ...] = Field(max_length=100)

    _metadata_has_no_controls = field_validator(
        "provider", "model", "model_version", "schema_version"
    )(_validate_text)

    @model_validator(mode="after")
    def validate_status(self) -> "OcrResultDraft":
        expected = OcrResultStatus.CANDIDATE if self.candidates else OcrResultStatus.EMPTY
        if self.status is not expected:
            raise ValueError("OCR result status does not match its candidates")
        return self

    @classmethod
    def from_parse_result(
        cls,
        result: OcrParseResult,
        *,
        provider: str = "local_paddleocr",
        model: str = "PP-OCRv6_medium",
        model_version: str = "PP-OCRv6_medium_det+rec",
        schema_version: str = "ocr-result.v1",
    ) -> "OcrResultDraft":
        return cls(
            provider=provider,
            model=model,
            model_version=model_version,
            schema_version=schema_version,
            confidence=result.confidence,
            status=OcrResultStatus(result.status),
            requires_manual_confirmation=True,
            candidates=tuple(
                OcrCandidateDraft(text=candidate.text, confidence=candidate.confidence)
                for candidate in result.candidates
            ),
        )


class OcrResultRepository(Protocol):
    def create_result(
        self,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        draft: OcrResultDraft,
        idempotency_key: str,
    ) -> tuple[OcrResult, bool]: ...

    def get_result(
        self, household_id: UUID, result_id: UUID, child_id: UUID
    ) -> tuple[OcrResult, list[OcrCandidate]]: ...


class PostgresOcrResultRepository:
    """PostgreSQL source of truth for normalized OCR result candidates."""

    def __init__(self, url: str | None = None) -> None:
        self._engine = create_engine(url or database_url(), pool_pre_ping=True)
        metadata = MetaData()
        self._captures = Table("captures", metadata, autoload_with=self._engine)
        self._results = Table("ocr_results", metadata, autoload_with=self._engine)
        self._candidates = Table("ocr_candidates", metadata, autoload_with=self._engine)
        self._idempotency = Table("idempotency_records", metadata, autoload_with=self._engine)
        self._audits = Table("audit_events", metadata, autoload_with=self._engine)

    @property
    def engine(self) -> Engine:
        return self._engine

    def close(self) -> None:
        self._engine.dispose()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _fingerprint(value: str) -> str:
        return sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _result(row: RowMapping) -> OcrResult:
        payload = dict(row)
        payload["confidence"] = float(payload["confidence"])
        return OcrResult.model_validate(payload)

    @staticmethod
    def _candidate(row: RowMapping) -> OcrCandidate:
        payload = dict(row)
        payload["confidence"] = float(payload["confidence"])
        return OcrCandidate.model_validate(payload)

    def create_result(
        self,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        draft: OcrResultDraft,
        idempotency_key: str,
    ) -> tuple[OcrResult, bool]:
        payload = draft.model_dump_json()
        operation = f"create_ocr_result:{capture_id}"
        with self._engine.begin() as connection:
            capture = self._capture_for_child(connection, household_id, capture_id, child_id)
            existing = self._idempotency_result(
                connection, household_id, operation, idempotency_key
            )
            if existing is not None:
                return self._replay_result(connection, existing, payload)
            if CaptureStatus(capture["status"]) is CaptureStatus.UPLOAD_PENDING:
                raise CaptureStateError

            result = OcrResult(
                id=uuid4(),
                capture_id=capture_id,
                household_id=household_id,
                child_id=child_id,
                provider=draft.provider,
                model=draft.model,
                model_version=draft.model_version,
                schema_version=draft.schema_version,
                confidence=draft.confidence,
                status=draft.status,
                requires_manual_confirmation=True,
                created_at=self._now(),
            )
            connection.execute(insert(self._results).values(**result.model_dump()))
            for sequence, candidate in enumerate(draft.candidates, start=1):
                connection.execute(
                    insert(self._candidates).values(
                        id=uuid4(),
                        result_id=result.id,
                        sequence=sequence,
                        text=candidate.text,
                        confidence=candidate.confidence,
                    )
                )
            self._store_idempotency(
                connection,
                household_id,
                operation,
                idempotency_key,
                payload,
                "ocr_result",
                result.id,
            )
            self._audit(connection, household_id, "ocr_result_created", result.id)
            return result, False

    def get_result(
        self, household_id: UUID, result_id: UUID, child_id: UUID
    ) -> tuple[OcrResult, list[OcrCandidate]]:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    select(self._results).where(
                        self._results.c.id == result_id,
                        self._results.c.household_id == household_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise LookupError
            result = self._result(row)
            if result.child_id != child_id:
                raise ChildAssignmentError
            candidates = [
                self._candidate(candidate)
                for candidate in connection.execute(
                    select(self._candidates)
                    .where(self._candidates.c.result_id == result_id)
                    .order_by(self._candidates.c.sequence)
                ).mappings()
            ]
            return result, candidates

    def _capture_for_child(
        self, connection: Connection, household_id: UUID, capture_id: UUID, child_id: UUID
    ) -> RowMapping:
        row = (
            connection.execute(
                select(self._captures)
                .where(
                    self._captures.c.id == capture_id,
                    self._captures.c.household_id == household_id,
                )
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise LookupError
        if row["child_id"] != child_id:
            raise ChildAssignmentError
        return row

    def _idempotency_result(
        self, connection: Connection, household_id: UUID, operation: str, key: str
    ) -> RowMapping | None:
        return (
            connection.execute(
                select(self._idempotency).where(
                    self._idempotency.c.household_id == household_id,
                    self._idempotency.c.operation == operation,
                    self._idempotency.c.idempotency_key == key,
                )
            )
            .mappings()
            .one_or_none()
        )

    def _store_idempotency(
        self,
        connection: Connection,
        household_id: UUID,
        operation: str,
        key: str,
        payload: str,
        resource_type: str,
        resource_id: UUID,
    ) -> None:
        connection.execute(
            insert(self._idempotency).values(
                household_id=household_id,
                operation=operation,
                idempotency_key=key,
                fingerprint=self._fingerprint(payload),
                resource_type=resource_type,
                resource_id=resource_id,
                created_at=self._now(),
            )
        )

    def _audit(
        self, connection: Connection, household_id: UUID, event_name: str, resource_id: UUID
    ) -> None:
        event = AuditEvent(
            id=uuid4(),
            household_id=household_id,
            event_name=event_name,
            resource_id=resource_id,
            recorded_at=self._now(),
        )
        connection.execute(insert(self._audits).values(**event.model_dump()))

    def _replay_result(
        self, connection: Connection, record: RowMapping, payload: str
    ) -> tuple[OcrResult, bool]:
        if (
            record["fingerprint"] != self._fingerprint(payload)
            or record["resource_type"] != "ocr_result"
        ):
            raise IdempotencyConflictError
        row = (
            connection.execute(
                select(self._results).where(self._results.c.id == record["resource_id"])
            )
            .mappings()
            .one()
        )
        return self._result(row), True
