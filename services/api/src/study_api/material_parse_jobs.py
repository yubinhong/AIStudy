"""Durable queue and worker for local curriculum PDF parsing."""

import os
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import MetaData, Table, create_engine, insert, select, update
from sqlalchemy.engine import Engine

from study_api.curriculum_limits import MAX_DOCUMENT_BYTES
from study_api.database import database_url
from study_api.domain.curriculum_knowledge import (
    CURRICULUM_BOOK_ANALYSIS_SCHEMA,
    CURRICULUM_BOOK_PROMPT,
    KnowledgeMapStatus,
)
from study_api.material_parser import (
    PARSER_VERSION,
    MaterialParseError,
    ParsedPage,
    parse_pdf,
)
from study_api.object_storage import (
    ObjectStorageConfig,
    ObjectStorageError,
    S3ObjectStorage,
)


class MaterialParseRepository(Protocol):
    def enqueue(
        self, household_id: UUID, child_id: UUID, material_id: UUID, snapshot_id: UUID
    ) -> None: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class ParseJob:
    id: UUID
    household_id: UUID
    child_id: UUID
    material_id: UUID
    snapshot_id: UUID
    status: str
    attempt: int
    parser_version: str
    error_code: str | None


class PostgresMaterialParseRepository:
    def __init__(self, url: str | None = None) -> None:
        self._engine = create_engine(url or database_url(), pool_pre_ping=True)
        metadata = MetaData()
        self._jobs = Table("material_parse_jobs", metadata, autoload_with=self._engine)
        self._materials = Table("learning_materials", metadata, autoload_with=self._engine)
        self._snapshots = Table("curriculum_snapshots", metadata, autoload_with=self._engine)
        self._chunks = Table("curriculum_chunks", metadata, autoload_with=self._engine)
        self._knowledge_maps = Table(
            "curriculum_knowledge_maps", metadata, autoload_with=self._engine
        )

    @property
    def engine(self) -> Engine:
        return self._engine

    def close(self) -> None:
        self._engine.dispose()

    def enqueue(
        self, household_id: UUID, child_id: UUID, material_id: UUID, snapshot_id: UUID
    ) -> None:
        now = datetime.now(UTC)
        with self._engine.begin() as connection:
            existing = connection.execute(
                select(self._jobs.c.id).where(self._jobs.c.material_id == material_id)
            ).scalar_one_or_none()
            if existing is not None:
                return
            connection.execute(
                insert(self._jobs).values(
                    id=uuid4(),
                    household_id=household_id,
                    child_id=child_id,
                    material_id=material_id,
                    snapshot_id=snapshot_id,
                    status="queued",
                    attempt=0,
                    parser_version=PARSER_VERSION,
                    error_code=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            connection.execute(
                update(self._materials)
                .where(self._materials.c.id == material_id)
                .values(status="queued")
            )

    def claim_next(self) -> ParseJob | None:
        with self._engine.begin() as connection:
            row = (
                connection.execute(
                    select(self._jobs)
                    .where(self._jobs.c.status == "queued")
                    .order_by(self._jobs.c.created_at, self._jobs.c.id)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            now = datetime.now(UTC)
            connection.execute(
                update(self._jobs)
                .where(self._jobs.c.id == row["id"])
                .values(status="parsing", attempt=int(row["attempt"]) + 1, updated_at=now)
            )
            connection.execute(
                update(self._materials)
                .where(self._materials.c.id == row["material_id"])
                .values(status="parsing")
            )
            return ParseJob(
                id=row["id"],
                household_id=row["household_id"],
                child_id=row["child_id"],
                material_id=row["material_id"],
                snapshot_id=row["snapshot_id"],
                status="parsing",
                attempt=int(row["attempt"]) + 1,
                parser_version=str(row["parser_version"]),
                error_code=None,
            )

    def complete(self, job: ParseJob, pages: tuple[ParsedPage, ...]) -> None:
        now = datetime.now(UTC)
        sections = [
            {
                "title": "AI 正在理解整本教材",
                "chapter": "待审核知识图谱",
                "learning_objectives": [
                    "结合页面图像归纳章节与知识点",
                    "等待家长审核后用于讲解和任务推荐",
                ],
            }
        ]
        with self._engine.begin() as connection:
            for index, page in enumerate(pages):
                connection.execute(
                    insert(self._chunks).values(
                        id=uuid4(),
                        household_id=job.household_id,
                        child_id=job.child_id,
                        material_id=job.material_id,
                        snapshot_id=job.snapshot_id,
                        page_number=page.page_number,
                        chunk_index=index,
                        title=page.title,
                        text=page.text,
                        text_sha256=page.text_sha256,
                        confidence=page.confidence,
                        parser_version=PARSER_VERSION,
                        created_at=now,
                    )
                )
            connection.execute(
                update(self._snapshots)
                .where(self._snapshots.c.id == job.snapshot_id)
                .values(sections=sections)
            )
            connection.execute(
                update(self._jobs)
                .where(self._jobs.c.id == job.id)
                .values(status="needs_review", error_code=None, updated_at=now)
            )
            connection.execute(
                update(self._materials)
                .where(self._materials.c.id == job.material_id)
                .values(status="needs_review")
            )
            existing_map = connection.execute(
                select(self._knowledge_maps.c.id).where(
                    self._knowledge_maps.c.snapshot_id == job.snapshot_id
                )
            ).scalar_one_or_none()
            if existing_map is None:
                connection.execute(
                    insert(self._knowledge_maps).values(
                        id=uuid4(),
                        household_id=job.household_id,
                        child_id=job.child_id,
                        material_id=job.material_id,
                        snapshot_id=job.snapshot_id,
                        status=KnowledgeMapStatus.QUEUED.value,
                        attempt=0,
                        book_summary=None,
                        chapters=[],
                        page_count=len(pages),
                        analyzed_page_count=0,
                        provider=None,
                        model=None,
                        schema_version=CURRICULUM_BOOK_ANALYSIS_SCHEMA,
                        prompt_version=CURRICULUM_BOOK_PROMPT,
                        input_fingerprint=None,
                        output_fingerprint=None,
                        latency_ms=None,
                        input_tokens=None,
                        output_tokens=None,
                        cost_cents=None,
                        error_code=None,
                        created_at=now,
                        updated_at=now,
                        reviewed_at=None,
                    )
                )

    def fail(self, job: ParseJob, code: str) -> None:
        now = datetime.now(UTC)
        status = (
            "needs_ocr"
            if code == "needs_ocr"
            else "quarantined"
            if code in {"unsafe_pdf_features", "encrypted_pdf_not_supported"}
            else "failed"
        )
        with self._engine.begin() as connection:
            connection.execute(
                update(self._jobs)
                .where(self._jobs.c.id == job.id)
                .values(status=status, error_code=code, updated_at=now)
            )
            connection.execute(
                update(self._materials)
                .where(self._materials.c.id == job.material_id)
                .values(status=status)
            )


def run_once(repository: PostgresMaterialParseRepository, storage: S3ObjectStorage) -> bool:
    job = repository.claim_next()
    if job is None:
        return False
    with repository._engine.connect() as connection:
        object_key = connection.execute(
            select(repository._materials.c.object_key).where(
                repository._materials.c.id == job.material_id
            )
        ).scalar_one_or_none()
    try:
        if not isinstance(object_key, str) or not object_key.startswith("curriculum/"):
            raise MaterialParseError("material_object_missing")
        data = storage.read_document(object_key, max_bytes=MAX_DOCUMENT_BYTES)
        pages = parse_pdf(data)
        repository.complete(job, pages)
    except MaterialParseError as error:
        repository.fail(job, error.code)
    except (ObjectStorageError, OSError):
        repository.fail(job, "material_storage_unavailable")
    except Exception:  # noqa: BLE001 - worker stores a stable failure state
        repository.fail(job, "material_parse_failed")
    return True


def main() -> int:
    repository = PostgresMaterialParseRepository()
    storage = S3ObjectStorage(ObjectStorageConfig.from_environment())
    try:
        watch = "--watch" in sys.argv[1:]
        while True:
            processed = run_once(repository, storage)
            if not watch:
                break
            if not processed:
                time.sleep(float(os.environ.get("MATERIAL_PARSE_POLL_INTERVAL_SECONDS", "2")))
        return 0
    finally:
        repository.close()
