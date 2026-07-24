"""Persistence boundary for unverified, human-reviewable question extraction."""

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import MetaData, Table, create_engine, insert, select
from sqlalchemy.engine import Engine, RowMapping

from study_api.database import database_url
from study_api.privacy_models import QuestionExtraction, QuestionExtractionRecord


class QuestionExtractionRepository(Protocol):
    def create(
        self,
        job_id: UUID,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        extraction: QuestionExtraction,
    ) -> tuple[QuestionExtractionRecord, bool]: ...

    def get(
        self, household_id: UUID, capture_id: UUID, extraction_id: UUID, child_id: UUID
    ) -> QuestionExtractionRecord: ...


class InMemoryQuestionExtractionRepository:
    def __init__(self) -> None:
        self._records: dict[UUID, QuestionExtractionRecord] = {}
        self._jobs: dict[UUID, UUID] = {}

    def create(
        self,
        job_id: UUID,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        extraction: QuestionExtraction,
    ) -> tuple[QuestionExtractionRecord, bool]:
        existing_id = self._jobs.get(job_id)
        if existing_id is not None:
            return self._records[existing_id], True
        record = QuestionExtractionRecord(
            id=uuid4(),
            capture_id=capture_id,
            household_id=household_id,
            child_id=child_id,
            extraction=extraction,
            created_at=datetime.now(UTC),
        )
        self._records[record.id] = record
        self._jobs[job_id] = record.id
        return record, False

    def get(
        self, household_id: UUID, capture_id: UUID, extraction_id: UUID, child_id: UUID
    ) -> QuestionExtractionRecord:
        record = self._records.get(extraction_id)
        if (
            record is None
            or record.household_id != household_id
            or record.capture_id != capture_id
            or record.child_id != child_id
        ):
            raise LookupError
        return record


class PostgresQuestionExtractionRepository:
    def __init__(self, url: str | None = None) -> None:
        self._engine = create_engine(url or database_url(), pool_pre_ping=True)
        metadata = MetaData()
        self._records = Table("question_extractions", metadata, autoload_with=self._engine)

    @property
    def engine(self) -> Engine:
        return self._engine

    def close(self) -> None:
        self._engine.dispose()

    @staticmethod
    def _record(row: RowMapping) -> QuestionExtractionRecord:
        payload = dict(row)
        payload["extraction"] = QuestionExtraction(
            schema_version=payload.pop("schema_version"),
            subject=payload.pop("subject"),
            question_text=payload.pop("question_text"),
            options=tuple(payload.pop("options")),
            formulas=tuple(payload.pop("formulas")),
            has_diagram=payload.pop("has_diagram"),
            has_handwriting=payload.pop("has_handwriting"),
            detected_answer=payload.pop("detected_answer"),
            answer_state=payload.pop("answer_state"),
            answer_state_confidence=float(payload.pop("answer_state_confidence")),
            answer_steps=tuple(payload.pop("answer_steps")),
            question_region_count=payload.pop("question_region_count"),
            confidence=float(payload.pop("confidence")),
            needs_confirmation=payload.pop("needs_confirmation"),
        )
        return QuestionExtractionRecord.model_validate(payload)

    def create(
        self,
        job_id: UUID,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        extraction: QuestionExtraction,
    ) -> tuple[QuestionExtractionRecord, bool]:
        with self._engine.begin() as connection:
            existing = (
                connection.execute(
                    select(self._records).where(self._records.c.image_analysis_job_id == job_id)
                )
                .mappings()
                .one_or_none()
            )
            if existing is not None:
                return self._record(existing), True
            record = QuestionExtractionRecord(
                id=uuid4(),
                capture_id=capture_id,
                household_id=household_id,
                child_id=child_id,
                extraction=extraction,
                created_at=datetime.now(UTC),
            )
            connection.execute(
                insert(self._records).values(
                    id=record.id,
                    image_analysis_job_id=job_id,
                    capture_id=capture_id,
                    household_id=household_id,
                    child_id=child_id,
                    schema_version=extraction.schema_version,
                    subject=extraction.subject,
                    question_text=extraction.question_text,
                    options=list(extraction.options),
                    formulas=list(extraction.formulas),
                    has_diagram=extraction.has_diagram,
                    has_handwriting=extraction.has_handwriting,
                    detected_answer=extraction.detected_answer,
                    answer_state=extraction.answer_state,
                    answer_state_confidence=extraction.answer_state_confidence,
                    answer_steps=list(extraction.answer_steps),
                    question_region_count=extraction.question_region_count,
                    confidence=extraction.confidence,
                    needs_confirmation=extraction.needs_confirmation,
                    created_at=record.created_at,
                )
            )
            return record, False

    def get(
        self, household_id: UUID, capture_id: UUID, extraction_id: UUID, child_id: UUID
    ) -> QuestionExtractionRecord:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    select(self._records).where(
                        self._records.c.id == extraction_id,
                        self._records.c.household_id == household_id,
                        self._records.c.capture_id == capture_id,
                        self._records.c.child_id == child_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise LookupError
        return self._record(row)
