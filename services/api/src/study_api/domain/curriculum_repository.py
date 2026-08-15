"""Household-owned curriculum import drafts and independently published snapshots."""

from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import MetaData, Table, create_engine, delete, insert, select, update
from sqlalchemy.engine import Engine

from study_api.curriculum_limits import MAX_DOCUMENT_BYTES
from study_api.database import database_url
from study_api.domain.models import Subject
from study_api.domain.repository import IdempotencyConflictError


class CurriculumSection(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=1, max_length=160)
    chapter: str = Field(min_length=1, max_length=120)
    learning_objectives: tuple[str, ...] = Field(min_length=1, max_length=12)


class ImportCurriculumRequest(BaseModel):
    subject: Subject = Subject.MATH
    filename: str = Field(min_length=1, max_length=160)
    media_type: str = Field(pattern=r"^(application/pdf|application/json)$")
    byte_size: int = Field(ge=0, le=MAX_DOCUMENT_BYTES)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    authorization_statement: str = Field(min_length=1, max_length=500)
    is_public_reusable: bool = False
    grade: int = Field(ge=1, le=6)
    textbook_version: str = Field(min_length=1, max_length=120)
    term: str = Field(min_length=1, max_length=40)
    sections: tuple[CurriculumSection, ...] = Field(min_length=1, max_length=200)


class CurriculumMaterial(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    household_id: UUID
    child_id: UUID
    subject: Subject
    filename: str
    media_type: str
    byte_size: int
    content_sha256: str
    authorization_statement: str
    is_public_reusable: bool = False
    status: str
    created_at: datetime
    object_key: str | None = Field(default=None, exclude=True)


class CurriculumSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    household_id: UUID
    child_id: UUID
    material_id: UUID
    subject: Subject
    grade: int
    textbook_version: str
    term: str
    sections: tuple[CurriculumSection, ...]
    status: str
    version: int
    created_at: datetime
    published_at: datetime | None = None
    reused_from_snapshot_id: UUID | None = None


class CurriculumChunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    household_id: UUID
    child_id: UUID
    material_id: UUID
    snapshot_id: UUID
    page_number: int = Field(ge=1)
    chunk_index: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=160)
    text: str = Field(min_length=1, max_length=40_000)
    confidence: float = Field(ge=0, le=1)
    parser_version: str = Field(min_length=1, max_length=80)
    created_at: datetime


class CurriculumParsedPage(BaseModel):
    """Parent-readable, page-scoped parsing output without storage internals."""

    model_config = ConfigDict(frozen=True)

    page_number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=160)
    text: str = Field(min_length=1, max_length=40_000)
    confidence: float = Field(ge=0, le=1)
    image_available: bool = False
    image_path: str | None = None


class CurriculumImportResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    material: CurriculumMaterial
    snapshot: CurriculumSnapshot


class CurriculumRepository(Protocol):
    def import_draft(
        self,
        household_id: UUID,
        child_id: UUID,
        request: ImportCurriculumRequest,
        idempotency_key: str,
        object_key: str | None = None,
        reused_from_snapshot_id: UUID | None = None,
    ) -> tuple[CurriculumImportResult, bool]: ...

    def find_public_reusable_snapshot(
        self, request: ImportCurriculumRequest
    ) -> CurriculumImportResult | None: ...

    def clone_parsed_content(
        self, source_snapshot_id: UUID, target: CurriculumImportResult
    ) -> None: ...

    def has_other_material_reference(self, object_key: str, material_id: UUID) -> bool: ...

    def list_snapshots(
        self, household_id: UUID, child_id: UUID, published_only: bool = False
    ) -> list[CurriculumSnapshot]: ...

    def publish(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID, idempotency_key: str
    ) -> tuple[CurriculumSnapshot, bool]: ...

    def get_material_for_snapshot(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID
    ) -> CurriculumMaterial | None: ...

    def delete_snapshot(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID, idempotency_key: str
    ) -> tuple[CurriculumMaterial | None, bool]: ...

    def search_chunks(
        self, household_id: UUID, child_id: UUID, query: str, limit: int = 3
    ) -> list[CurriculumChunk]: ...

    def list_chunks(
        self,
        household_id: UUID,
        child_id: UUID,
        snapshot_id: UUID,
    ) -> list[CurriculumChunk]: ...

    def list_review_chunks(
        self,
        household_id: UUID,
        child_id: UUID,
        snapshot_id: UUID,
    ) -> list[CurriculumChunk]: ...


def _fingerprint(request: BaseModel) -> str:
    return sha256(request.model_dump_json().encode()).hexdigest()


def _contains_unparsed_document(snapshot: CurriculumSnapshot) -> bool:
    return any(section.chapter == "待解析文档" for section in snapshot.sections)


class InMemoryCurriculumRepository:
    def __init__(self) -> None:
        self._materials: dict[UUID, CurriculumMaterial] = {}
        self._snapshots: dict[UUID, CurriculumSnapshot] = {}
        self._receipts: dict[tuple[UUID, str, str], tuple[str, UUID]] = {}

    def import_draft(
        self,
        household_id: UUID,
        child_id: UUID,
        request: ImportCurriculumRequest,
        idempotency_key: str,
        object_key: str | None = None,
        reused_from_snapshot_id: UUID | None = None,
    ) -> tuple[CurriculumImportResult, bool]:
        operation = f"curriculum_import:{child_id}"
        fingerprint = _fingerprint(request)
        key = (household_id, operation, idempotency_key)
        existing = self._receipts.get(key)
        if existing is not None:
            if existing[0] != fingerprint:
                raise IdempotencyConflictError
            snapshot = self._snapshots[existing[1]]
            return CurriculumImportResult(
                material=self._materials[snapshot.material_id], snapshot=snapshot
            ), True
        now = datetime.now(UTC)
        material = CurriculumMaterial(
            id=uuid4(),
            household_id=household_id,
            child_id=child_id,
            subject=request.subject,
            filename=request.filename,
            media_type=request.media_type,
            byte_size=request.byte_size,
            content_sha256=request.content_sha256,
            authorization_statement=request.authorization_statement,
            is_public_reusable=request.is_public_reusable,
            status="uploaded" if object_key else "parsed",
            created_at=now,
            object_key=object_key,
        )
        version = (
            sum(
                1
                for snapshot in self._snapshots.values()
                if snapshot.child_id == child_id
                and snapshot.subject is request.subject
                and snapshot.textbook_version == request.textbook_version
            )
            + 1
        )
        snapshot = CurriculumSnapshot(
            id=uuid4(),
            household_id=household_id,
            child_id=child_id,
            material_id=material.id,
            subject=request.subject,
            grade=request.grade,
            textbook_version=request.textbook_version,
            term=request.term,
            sections=request.sections,
            status="draft",
            version=version,
            created_at=now,
            reused_from_snapshot_id=reused_from_snapshot_id,
        )
        self._materials[material.id] = material
        self._snapshots[snapshot.id] = snapshot
        self._receipts[key] = (fingerprint, snapshot.id)
        return CurriculumImportResult(material=material, snapshot=snapshot), False

    def find_public_reusable_snapshot(
        self, request: ImportCurriculumRequest
    ) -> CurriculumImportResult | None:
        for snapshot in self._snapshots.values():
            material = self._materials[snapshot.material_id]
            if (
                material.is_public_reusable
                and material.subject is request.subject
                and snapshot.subject is request.subject
                and material.content_sha256 == request.content_sha256
                and material.media_type == request.media_type
                and material.byte_size == request.byte_size
                and material.object_key
            ):
                return CurriculumImportResult(material=material, snapshot=snapshot)
        return None

    def clone_parsed_content(
        self, source_snapshot_id: UUID, target: CurriculumImportResult
    ) -> None:
        source = self._snapshots[source_snapshot_id]
        self._snapshots[target.snapshot.id] = target.snapshot.model_copy(
            update={
                "sections": source.sections,
                "textbook_version": source.textbook_version,
                "term": source.term,
            }
        )
        self._materials[target.material.id] = target.material.model_copy(
            update={"status": "needs_review"}
        )

    def has_other_material_reference(self, object_key: str, material_id: UUID) -> bool:
        return any(
            material.id != material_id and material.object_key == object_key
            for material in self._materials.values()
        )

    def list_snapshots(
        self, household_id: UUID, child_id: UUID, published_only: bool = False
    ) -> list[CurriculumSnapshot]:
        values = [
            snapshot
            for snapshot in self._snapshots.values()
            if snapshot.household_id == household_id
            and snapshot.child_id == child_id
            and (not published_only or snapshot.status == "published")
        ]
        return sorted(values, key=lambda value: (value.created_at, value.version), reverse=True)

    def publish(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID, idempotency_key: str
    ) -> tuple[CurriculumSnapshot, bool]:
        operation = f"curriculum_publish:{snapshot_id}"
        key = (household_id, operation, idempotency_key)
        fingerprint = sha256(f"{child_id}:{snapshot_id}".encode()).hexdigest()
        existing = self._receipts.get(key)
        if existing is not None:
            if existing[0] != fingerprint:
                raise IdempotencyConflictError
            return self._snapshots[existing[1]], True
        current = self._snapshots.get(snapshot_id)
        if current is None or current.household_id != household_id or current.child_id != child_id:
            raise LookupError
        if current.status != "draft":
            raise ValueError("only a draft curriculum snapshot can be published")
        if _contains_unparsed_document(current):
            raise ValueError("curriculum document must be parsed before publication")
        now = datetime.now(UTC)
        published = current.model_copy(update={"status": "published", "published_at": now})
        self._snapshots[snapshot_id] = published
        self._materials[current.material_id] = self._materials[current.material_id].model_copy(
            update={"status": "published"}
        )
        self._receipts[key] = (fingerprint, snapshot_id)
        return published, False

    def get_material_for_snapshot(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID
    ) -> CurriculumMaterial | None:
        snapshot = self._snapshots.get(snapshot_id)
        if (
            snapshot is None
            or snapshot.household_id != household_id
            or snapshot.child_id != child_id
        ):
            return None
        return self._materials.get(snapshot.material_id)

    def delete_snapshot(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID, idempotency_key: str
    ) -> tuple[CurriculumMaterial | None, bool]:
        operation = f"curriculum_delete:{snapshot_id}"
        key = (household_id, operation, idempotency_key)
        fingerprint = sha256(f"{child_id}:{snapshot_id}".encode()).hexdigest()
        existing = self._receipts.get(key)
        if existing is not None:
            if existing[0] != fingerprint:
                raise IdempotencyConflictError
            return None, True
        snapshot = self._snapshots.get(snapshot_id)
        if (
            snapshot is None
            or snapshot.household_id != household_id
            or snapshot.child_id != child_id
        ):
            raise LookupError
        material = self._materials.pop(snapshot.material_id)
        del self._snapshots[snapshot_id]
        for receipt_key, receipt in list(self._receipts.items()):
            if receipt[1] == snapshot_id:
                del self._receipts[receipt_key]
        self._receipts[key] = (fingerprint, snapshot_id)
        return material, False

    def search_chunks(
        self, household_id: UUID, child_id: UUID, query: str, limit: int = 3
    ) -> list[CurriculumChunk]:
        del household_id, child_id, query, limit
        return []

    def list_chunks(
        self,
        household_id: UUID,
        child_id: UUID,
        snapshot_id: UUID,
    ) -> list[CurriculumChunk]:
        del household_id, child_id, snapshot_id
        return []

    def list_review_chunks(
        self,
        household_id: UUID,
        child_id: UUID,
        snapshot_id: UUID,
    ) -> list[CurriculumChunk]:
        del household_id, child_id, snapshot_id
        return []


class PostgresCurriculumRepository:
    def __init__(self, url: str | None = None) -> None:
        self._engine = create_engine(url or database_url(), pool_pre_ping=True)
        metadata = MetaData()
        self._materials = Table("learning_materials", metadata, autoload_with=self._engine)
        self._snapshots = Table("curriculum_snapshots", metadata, autoload_with=self._engine)
        self._idempotency = Table("idempotency_records", metadata, autoload_with=self._engine)
        self._chunks = Table("curriculum_chunks", metadata, autoload_with=self._engine)

    @property
    def engine(self) -> Engine:
        return self._engine

    def close(self) -> None:
        self._engine.dispose()

    @staticmethod
    def _material(row: dict) -> CurriculumMaterial:
        return CurriculumMaterial.model_validate(row)

    @staticmethod
    def _snapshot(row: dict) -> CurriculumSnapshot:
        values = dict(row)
        values["sections"] = tuple(
            CurriculumSection.model_validate(item) for item in values["sections"]
        )
        return CurriculumSnapshot.model_validate(values)

    def _read(self, connection, snapshot_id: UUID) -> CurriculumImportResult:
        snapshot_row = (
            connection.execute(select(self._snapshots).where(self._snapshots.c.id == snapshot_id))
            .mappings()
            .one()
        )
        material_row = (
            connection.execute(
                select(self._materials).where(self._materials.c.id == snapshot_row["material_id"])
            )
            .mappings()
            .one()
        )
        return CurriculumImportResult(
            material=self._material(dict(material_row)),
            snapshot=self._snapshot(dict(snapshot_row)),
        )

    def import_draft(
        self,
        household_id: UUID,
        child_id: UUID,
        request: ImportCurriculumRequest,
        idempotency_key: str,
        object_key: str | None = None,
        reused_from_snapshot_id: UUID | None = None,
    ) -> tuple[CurriculumImportResult, bool]:
        operation = f"curriculum_import:{child_id}"
        fingerprint = _fingerprint(request)
        now = datetime.now(UTC)
        with self._engine.begin() as connection:
            receipt = (
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
            if receipt is not None:
                if receipt["fingerprint"] != fingerprint:
                    raise IdempotencyConflictError
                return self._read(connection, receipt["resource_id"]), True
            material_id, snapshot_id = uuid4(), uuid4()
            version = (
                connection.execute(
                    select(self._snapshots.c.version)
                    .where(
                        self._snapshots.c.household_id == household_id,
                        self._snapshots.c.child_id == child_id,
                        self._snapshots.c.subject == request.subject.value,
                        self._snapshots.c.textbook_version == request.textbook_version,
                    )
                    .order_by(self._snapshots.c.version.desc())
                    .limit(1)
                ).scalar_one_or_none()
                or 0
            ) + 1
            connection.execute(
                insert(self._materials).values(
                    id=material_id,
                    household_id=household_id,
                    child_id=child_id,
                    subject=request.subject.value,
                    filename=request.filename,
                    media_type=request.media_type,
                    byte_size=request.byte_size,
                    content_sha256=request.content_sha256,
                    authorization_statement=request.authorization_statement,
                    is_public_reusable=request.is_public_reusable,
                    status="uploaded" if object_key else "parsed",
                    created_at=now,
                    object_key=object_key,
                )
            )
            connection.execute(
                insert(self._snapshots).values(
                    id=snapshot_id,
                    household_id=household_id,
                    child_id=child_id,
                    material_id=material_id,
                    subject=request.subject.value,
                    grade=request.grade,
                    textbook_version=request.textbook_version,
                    term=request.term,
                    sections=[section.model_dump(mode="json") for section in request.sections],
                    status="draft",
                    version=version,
                    created_at=now,
                    published_at=None,
                    reused_from_snapshot_id=reused_from_snapshot_id,
                )
            )
            connection.execute(
                insert(self._idempotency).values(
                    household_id=household_id,
                    operation=operation,
                    idempotency_key=idempotency_key,
                    fingerprint=fingerprint,
                    resource_type="curriculum_snapshot",
                    resource_id=snapshot_id,
                    created_at=now,
                )
            )
            return self._read(connection, snapshot_id), False

    def find_public_reusable_snapshot(
        self, request: ImportCurriculumRequest
    ) -> CurriculumImportResult | None:
        # No caller receives the source identity. It is only used internally to
        # attach an already approved public textbook to a new private snapshot.
        from study_api.domain.curriculum_knowledge import KnowledgeMapStatus

        # Reflect the optional analysis tables lazily so older development
        # databases can still construct this repository before migration.
        metadata = MetaData()
        maps = Table("curriculum_knowledge_maps", metadata, autoload_with=self._engine)
        statement = (
            select(self._snapshots.c.id)
            .join(self._materials, self._materials.c.id == self._snapshots.c.material_id)
            .join(maps, maps.c.snapshot_id == self._snapshots.c.id)
            .where(
                self._materials.c.is_public_reusable.is_(True),
                self._materials.c.content_sha256 == request.content_sha256,
                self._materials.c.media_type == request.media_type,
                self._materials.c.byte_size == request.byte_size,
                self._materials.c.subject == request.subject.value,
                self._snapshots.c.subject == request.subject.value,
                self._materials.c.object_key.is_not(None),
                maps.c.status == KnowledgeMapStatus.APPROVED.value,
            )
            .order_by(maps.c.reviewed_at.desc().nullslast(), self._snapshots.c.created_at.desc())
            .limit(1)
        )
        with self._engine.connect() as connection:
            snapshot_id = connection.execute(statement).scalar_one_or_none()
            return self._read(connection, snapshot_id) if snapshot_id is not None else None

    def clone_parsed_content(
        self, source_snapshot_id: UUID, target: CurriculumImportResult
    ) -> None:
        """Copy text facts into a new tenant snapshot without another PDF parse."""

        now = datetime.now(UTC)
        with self._engine.begin() as connection:
            source = (
                connection.execute(
                    select(self._snapshots).where(self._snapshots.c.id == source_snapshot_id)
                )
                .mappings()
                .one()
            )
            rows = (
                connection.execute(
                    select(self._chunks).where(self._chunks.c.snapshot_id == source_snapshot_id)
                )
                .mappings()
                .all()
            )
            for row in rows:
                values = dict(row)
                values.update(
                    id=uuid4(),
                    household_id=target.snapshot.household_id,
                    child_id=target.snapshot.child_id,
                    material_id=target.material.id,
                    snapshot_id=target.snapshot.id,
                    created_at=now,
                )
                connection.execute(insert(self._chunks).values(**values))
            connection.execute(
                update(self._snapshots)
                .where(self._snapshots.c.id == target.snapshot.id)
                .values(
                    sections=source["sections"],
                    textbook_version=source["textbook_version"],
                    term=source["term"],
                )
            )
            connection.execute(
                update(self._materials)
                .where(self._materials.c.id == target.material.id)
                .values(status="needs_review")
            )

    def has_other_material_reference(self, object_key: str, material_id: UUID) -> bool:
        with self._engine.connect() as connection:
            return (
                connection.execute(
                    select(self._materials.c.id)
                    .where(
                        self._materials.c.object_key == object_key,
                        self._materials.c.id != material_id,
                    )
                    .limit(1)
                ).scalar_one_or_none()
                is not None
            )

    def list_snapshots(
        self, household_id: UUID, child_id: UUID, published_only: bool = False
    ) -> list[CurriculumSnapshot]:
        statement = select(self._snapshots).where(
            self._snapshots.c.household_id == household_id,
            self._snapshots.c.child_id == child_id,
        )
        if published_only:
            statement = statement.where(self._snapshots.c.status == "published")
        statement = statement.order_by(
            self._snapshots.c.created_at.desc(), self._snapshots.c.version.desc()
        )
        with self._engine.connect() as connection:
            return [self._snapshot(dict(row)) for row in connection.execute(statement).mappings()]

    def publish(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID, idempotency_key: str
    ) -> tuple[CurriculumSnapshot, bool]:
        operation = f"curriculum_publish:{snapshot_id}"
        fingerprint = sha256(f"{child_id}:{snapshot_id}".encode()).hexdigest()
        now = datetime.now(UTC)
        with self._engine.begin() as connection:
            receipt = (
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
            if receipt is not None:
                if receipt["fingerprint"] != fingerprint:
                    raise IdempotencyConflictError
                return self._snapshot(
                    dict(
                        connection.execute(
                            select(self._snapshots).where(
                                self._snapshots.c.id == receipt["resource_id"]
                            )
                        )
                        .mappings()
                        .one()
                    )
                ), True
            current = (
                connection.execute(
                    select(self._snapshots)
                    .where(
                        self._snapshots.c.id == snapshot_id,
                        self._snapshots.c.household_id == household_id,
                        self._snapshots.c.child_id == child_id,
                    )
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if current is None:
                raise LookupError
            if current["status"] != "draft":
                raise ValueError("only a draft curriculum snapshot can be published")
            if _contains_unparsed_document(self._snapshot(dict(current))):
                raise ValueError("curriculum document must be parsed before publication")
            connection.execute(
                update(self._snapshots)
                .where(self._snapshots.c.id == snapshot_id)
                .values(status="published", published_at=now)
            )
            connection.execute(
                update(self._materials)
                .where(self._materials.c.id == current["material_id"])
                .values(status="published")
            )
            connection.execute(
                insert(self._idempotency).values(
                    household_id=household_id,
                    operation=operation,
                    idempotency_key=idempotency_key,
                    fingerprint=fingerprint,
                    resource_type="curriculum_snapshot",
                    resource_id=snapshot_id,
                    created_at=now,
                )
            )
            row = (
                connection.execute(
                    select(self._snapshots).where(self._snapshots.c.id == snapshot_id)
                )
                .mappings()
                .one()
            )
            return self._snapshot(dict(row)), False

    def get_material_for_snapshot(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID
    ) -> CurriculumMaterial | None:
        statement = (
            select(self._materials)
            .join(
                self._snapshots,
                self._snapshots.c.material_id == self._materials.c.id,
            )
            .where(
                self._snapshots.c.id == snapshot_id,
                self._snapshots.c.household_id == household_id,
                self._snapshots.c.child_id == child_id,
            )
        )
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        return self._material(dict(row)) if row is not None else None

    def delete_snapshot(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID, idempotency_key: str
    ) -> tuple[CurriculumMaterial | None, bool]:
        operation = f"curriculum_delete:{snapshot_id}"
        fingerprint = sha256(f"{child_id}:{snapshot_id}".encode()).hexdigest()
        now = datetime.now(UTC)
        with self._engine.begin() as connection:
            receipt = (
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
            if receipt is not None:
                if receipt["fingerprint"] != fingerprint:
                    raise IdempotencyConflictError
                return None, True
            row = (
                connection.execute(
                    select(self._snapshots.c.material_id)
                    .where(
                        self._snapshots.c.id == snapshot_id,
                        self._snapshots.c.household_id == household_id,
                        self._snapshots.c.child_id == child_id,
                    )
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise LookupError
            material = self._material(
                dict(
                    connection.execute(
                        select(self._materials)
                        .where(self._materials.c.id == row["material_id"])
                        .with_for_update()
                    )
                    .mappings()
                    .one()
                )
            )
            connection.execute(
                delete(self._idempotency).where(
                    self._idempotency.c.household_id == household_id,
                    self._idempotency.c.resource_id == snapshot_id,
                )
            )
            connection.execute(delete(self._snapshots).where(self._snapshots.c.id == snapshot_id))
            connection.execute(delete(self._materials).where(self._materials.c.id == material.id))
            connection.execute(
                insert(self._idempotency).values(
                    household_id=household_id,
                    operation=operation,
                    idempotency_key=idempotency_key,
                    fingerprint=fingerprint,
                    resource_type="curriculum_snapshot_deletion",
                    resource_id=snapshot_id,
                    created_at=now,
                )
            )
            return material, False

    def search_chunks(
        self, household_id: UUID, child_id: UUID, query: str, limit: int = 3
    ) -> list[CurriculumChunk]:
        terms = [term.strip() for term in query.split() if len(term.strip()) >= 2][:6]
        statement = (
            select(self._chunks)
            .join(
                self._snapshots,
                self._snapshots.c.id == self._chunks.c.snapshot_id,
            )
            .where(
                self._chunks.c.household_id == household_id,
                self._chunks.c.child_id == child_id,
                self._snapshots.c.status == "published",
            )
            .order_by(self._chunks.c.confidence.desc(), self._chunks.c.page_number)
            .limit(max(1, min(limit, 5)))
        )
        if terms:
            from sqlalchemy import or_

            statement = statement.where(
                or_(*[self._chunks.c.text.ilike(f"%{term}%") for term in terms])
            )
        with self._engine.connect() as connection:
            return [
                CurriculumChunk.model_validate(dict(row))
                for row in connection.execute(statement).mappings()
            ]

    def list_chunks(
        self,
        household_id: UUID,
        child_id: UUID,
        snapshot_id: UUID,
    ) -> list[CurriculumChunk]:
        """Read every parsed chunk from one published snapshot for local ranking."""

        statement = (
            select(self._chunks)
            .join(
                self._snapshots,
                self._snapshots.c.id == self._chunks.c.snapshot_id,
            )
            .where(
                self._chunks.c.household_id == household_id,
                self._chunks.c.child_id == child_id,
                self._chunks.c.snapshot_id == snapshot_id,
                self._snapshots.c.status == "published",
            )
            .order_by(self._chunks.c.page_number, self._chunks.c.chunk_index)
        )
        with self._engine.connect() as connection:
            return [
                CurriculumChunk.model_validate(dict(row))
                for row in connection.execute(statement).mappings()
            ]

    def list_review_chunks(
        self,
        household_id: UUID,
        child_id: UUID,
        snapshot_id: UUID,
    ) -> list[CurriculumChunk]:
        """Read one parent's draft or published page-level parsing result."""

        statement = (
            select(self._chunks)
            .join(
                self._snapshots,
                self._snapshots.c.id == self._chunks.c.snapshot_id,
            )
            .where(
                self._chunks.c.household_id == household_id,
                self._chunks.c.child_id == child_id,
                self._chunks.c.snapshot_id == snapshot_id,
            )
            .order_by(self._chunks.c.page_number, self._chunks.c.chunk_index)
        )
        with self._engine.connect() as connection:
            return [
                CurriculumChunk.model_validate(dict(row))
                for row in connection.execute(statement).mappings()
            ]
