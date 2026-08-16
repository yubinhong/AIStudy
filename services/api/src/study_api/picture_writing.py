"""Independent persistence boundary for picture-writing guidance.

This deliberately stores no question extraction, answer, composition, or grade.
"""

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import MetaData, Table, create_engine, insert, select
from sqlalchemy.engine import Engine, RowMapping

from study_api.database import database_url
from study_api.privacy_models import PictureWritingGuide, PictureWritingGuideRecord


class PictureWritingRepository(Protocol):
    def create(
        self,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        idempotency_key: str,
        guide: PictureWritingGuide,
        *,
        provider: str,
        model: str,
    ) -> tuple[PictureWritingGuideRecord, bool]: ...

    def get(
        self, household_id: UUID, capture_id: UUID, child_id: UUID, guide_id: UUID
    ) -> PictureWritingGuideRecord: ...


class InMemoryPictureWritingRepository:
    def __init__(self) -> None:
        self._records: dict[UUID, PictureWritingGuideRecord] = {}
        self._keys: dict[tuple[UUID, UUID, UUID, str], UUID] = {}

    def create(
        self,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        idempotency_key: str,
        guide: PictureWritingGuide,
        *,
        provider: str,
        model: str,
    ) -> tuple[PictureWritingGuideRecord, bool]:
        key = (household_id, capture_id, child_id, idempotency_key)
        existing = self._keys.get(key)
        if existing is not None:
            return self._records[existing], True
        record = PictureWritingGuideRecord(
            id=uuid4(),
            capture_id=capture_id,
            household_id=household_id,
            child_id=child_id,
            guide=guide,
            provider=provider,
            model=model,
            created_at=datetime.now(UTC),
        )
        self._records[record.id] = record
        self._keys[key] = record.id
        return record, False

    def get(
        self, household_id: UUID, capture_id: UUID, child_id: UUID, guide_id: UUID
    ) -> PictureWritingGuideRecord:
        record = self._records.get(guide_id)
        if record is None or (
            record.household_id,
            record.capture_id,
            record.child_id,
        ) != (household_id, capture_id, child_id):
            raise LookupError
        return record


class PostgresPictureWritingRepository:
    def __init__(self, url: str | None = None) -> None:
        self._engine = create_engine(url or database_url(), pool_pre_ping=True)
        metadata = MetaData()
        self._records = Table("picture_writing_guides", metadata, autoload_with=self._engine)

    @property
    def engine(self) -> Engine:
        return self._engine

    def close(self) -> None:
        self._engine.dispose()

    @staticmethod
    def _record(row: RowMapping) -> PictureWritingGuideRecord:
        payload = dict(row)
        payload["guide"] = PictureWritingGuide.model_validate(payload.pop("guide_json"))
        return PictureWritingGuideRecord.model_validate(payload)

    def create(
        self,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        idempotency_key: str,
        guide: PictureWritingGuide,
        *,
        provider: str,
        model: str,
    ) -> tuple[PictureWritingGuideRecord, bool]:
        with self._engine.begin() as connection:
            existing = (
                connection.execute(
                    select(self._records).where(
                        self._records.c.household_id == household_id,
                        self._records.c.capture_id == capture_id,
                        self._records.c.child_id == child_id,
                        self._records.c.idempotency_key == idempotency_key,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if existing is not None:
                return self._record(existing), True
            record = PictureWritingGuideRecord(
                id=uuid4(),
                capture_id=capture_id,
                household_id=household_id,
                child_id=child_id,
                guide=guide,
                provider=provider,
                model=model,
                created_at=datetime.now(UTC),
            )
            connection.execute(
                insert(self._records).values(
                    id=record.id,
                    household_id=household_id,
                    child_id=child_id,
                    capture_id=capture_id,
                    idempotency_key=idempotency_key,
                    guide_json=guide.model_dump(mode="json"),
                    provider=provider,
                    model=model,
                    policy_version=record.policy_version,
                    created_at=record.created_at,
                )
            )
            return record, False

    def get(
        self, household_id: UUID, capture_id: UUID, child_id: UUID, guide_id: UUID
    ) -> PictureWritingGuideRecord:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    select(self._records).where(
                        self._records.c.id == guide_id,
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
