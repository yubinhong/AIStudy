"""Persistence boundary for human-confirmed question facts."""

from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import MetaData, Table, create_engine, insert, select
from sqlalchemy.engine import Engine, RowMapping

from study_api.database import database_url
from study_api.domain.repository import IdempotencyConflictError
from study_api.privacy_models import VerifiedQuestion, VerifyQuestionRequest


class VerifiedQuestionRepository(Protocol):
    def create(
        self,
        household_id: UUID,
        child_id: UUID,
        capture_id: UUID,
        extraction_id: UUID,
        request: VerifyQuestionRequest,
        verified_by: str,
        idempotency_key: str,
    ) -> tuple[VerifiedQuestion, bool]: ...

    def get(
        self, household_id: UUID, child_id: UUID, capture_id: UUID, extraction_id: UUID
    ) -> VerifiedQuestion: ...

    def get_by_id(
        self, household_id: UUID, child_id: UUID, verified_question_id: UUID
    ) -> VerifiedQuestion: ...


def _fingerprint(request: VerifyQuestionRequest, verified_by: str) -> str:
    return sha256(f"{request.model_dump_json()}:{verified_by}".encode()).hexdigest()


class InMemoryVerifiedQuestionRepository:
    def __init__(self) -> None:
        self._records: dict[UUID, VerifiedQuestion] = {}
        self._by_extraction: dict[UUID, UUID] = {}
        self._scope: dict[UUID, tuple[UUID, UUID]] = {}
        self._idempotency: dict[tuple[UUID, str, str], tuple[str, UUID]] = {}

    def create(
        self,
        household_id: UUID,
        child_id: UUID,
        capture_id: UUID,
        extraction_id: UUID,
        request: VerifyQuestionRequest,
        verified_by: str,
        idempotency_key: str,
    ) -> tuple[VerifiedQuestion, bool]:
        operation = f"verify_question:{extraction_id}"
        key = (household_id, operation, idempotency_key)
        fingerprint = _fingerprint(request, verified_by)
        replay = self._idempotency.get(key)
        if replay is not None:
            if replay[0] != fingerprint:
                raise IdempotencyConflictError
            return self._records[replay[1]], True
        existing_id = self._by_extraction.get(extraction_id)
        if existing_id is not None:
            existing = self._records[existing_id]
            if existing.capture_id != capture_id or self._scope[existing_id] != (
                household_id,
                child_id,
            ):
                raise LookupError
            self._idempotency[key] = (fingerprint, existing_id)
            return existing, True
        record = VerifiedQuestion(
            id=uuid4(),
            capture_id=capture_id,
            extraction_id=extraction_id,
            version=1,
            subject="math",
            question_text=request.question_text,
            options=request.options,
            formulas=request.formulas,
            has_diagram=request.has_diagram,
            has_handwriting=request.has_handwriting,
            answer_text=request.answer_text,
            answer_state=request.answer_state,
            answer_state_confidence=request.answer_state_confidence,
            answer_steps=request.answer_steps,
            evidence_confirmed=request.evidence_confirmed,
            verified_by=verified_by,  # type: ignore[arg-type]
            verified_at=datetime.now(UTC),
        )
        self._records[record.id] = record
        self._by_extraction[extraction_id] = record.id
        self._scope[record.id] = (household_id, child_id)
        self._idempotency[key] = (fingerprint, record.id)
        return record, False

    def get(
        self, household_id: UUID, child_id: UUID, capture_id: UUID, extraction_id: UUID
    ) -> VerifiedQuestion:
        record_id = self._by_extraction.get(extraction_id)
        record = self._records.get(record_id) if record_id else None
        if (
            record is None
            or record.capture_id != capture_id
            or self._scope.get(record.id) != (household_id, child_id)
        ):
            raise LookupError
        return record

    def get_by_id(
        self, household_id: UUID, child_id: UUID, verified_question_id: UUID
    ) -> VerifiedQuestion:
        record = self._records.get(verified_question_id)
        if record is None or self._scope.get(record.id) != (household_id, child_id):
            raise LookupError
        return record


class PostgresVerifiedQuestionRepository:
    def __init__(self, url: str | None = None) -> None:
        self._engine = create_engine(url or database_url(), pool_pre_ping=True)
        metadata = MetaData()
        self._records = Table("verified_questions", metadata, autoload_with=self._engine)
        self._idempotency = Table("idempotency_records", metadata, autoload_with=self._engine)

    @property
    def engine(self) -> Engine:
        return self._engine

    def close(self) -> None:
        self._engine.dispose()

    @staticmethod
    def _record(row: RowMapping) -> VerifiedQuestion:
        payload = dict(row)
        payload["options"] = tuple(payload["options"])
        payload["formulas"] = tuple(payload["formulas"])
        payload["answer_steps"] = tuple(payload["answer_steps"])
        payload.pop("household_id", None)
        payload.pop("child_id", None)
        return VerifiedQuestion.model_validate(payload)

    def create(
        self,
        household_id: UUID,
        child_id: UUID,
        capture_id: UUID,
        extraction_id: UUID,
        request: VerifyQuestionRequest,
        verified_by: str,
        idempotency_key: str,
    ) -> tuple[VerifiedQuestion, bool]:
        operation = f"verify_question:{extraction_id}"
        fingerprint = _fingerprint(request, verified_by)
        with self._engine.begin() as connection:
            idem = (
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
            if idem is not None:
                if idem["fingerprint"] != fingerprint:
                    raise IdempotencyConflictError
                row = (
                    connection.execute(
                        select(self._records).where(self._records.c.id == idem["resource_id"])
                    )
                    .mappings()
                    .one()
                )
                return self._record(row), True
            existing = (
                connection.execute(
                    select(self._records).where(
                        self._records.c.household_id == household_id,
                        self._records.c.child_id == child_id,
                        self._records.c.capture_id == capture_id,
                        self._records.c.extraction_id == extraction_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if existing is not None:
                record = self._record(existing)
                connection.execute(
                    insert(self._idempotency).values(
                        household_id=household_id,
                        operation=operation,
                        idempotency_key=idempotency_key,
                        fingerprint=fingerprint,
                        resource_type="verified_question",
                        resource_id=record.id,
                        created_at=datetime.now(UTC),
                    )
                )
                return record, True
            record = VerifiedQuestion(
                id=uuid4(),
                capture_id=capture_id,
                extraction_id=extraction_id,
                version=1,
                subject="math",
                question_text=request.question_text,
                options=request.options,
                formulas=request.formulas,
                has_diagram=request.has_diagram,
                has_handwriting=request.has_handwriting,
                answer_text=request.answer_text,
                answer_state=request.answer_state,
                answer_state_confidence=request.answer_state_confidence,
                answer_steps=request.answer_steps,
                evidence_confirmed=request.evidence_confirmed,
                verified_by=verified_by,  # type: ignore[arg-type]
                verified_at=datetime.now(UTC),
            )
            connection.execute(
                insert(self._records).values(
                    **record.model_dump(),
                    household_id=household_id,
                    child_id=child_id,
                )
            )
            connection.execute(
                insert(self._idempotency).values(
                    household_id=household_id,
                    operation=operation,
                    idempotency_key=idempotency_key,
                    fingerprint=fingerprint,
                    resource_type="verified_question",
                    resource_id=record.id,
                    created_at=datetime.now(UTC),
                )
            )
            return record, False

    def get(
        self, household_id: UUID, child_id: UUID, capture_id: UUID, extraction_id: UUID
    ) -> VerifiedQuestion:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    select(self._records).where(
                        self._records.c.household_id == household_id,
                        self._records.c.child_id == child_id,
                        self._records.c.capture_id == capture_id,
                        self._records.c.extraction_id == extraction_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise LookupError
        return self._record(row)

    def get_by_id(
        self, household_id: UUID, child_id: UUID, verified_question_id: UUID
    ) -> VerifiedQuestion:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    select(self._records).where(
                        self._records.c.id == verified_question_id,
                        self._records.c.household_id == household_id,
                        self._records.c.child_id == child_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise LookupError
        return self._record(row)
