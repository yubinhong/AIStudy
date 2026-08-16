"""Durable multimodal curriculum analysis and parent-reviewed knowledge maps."""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import MetaData, Table, create_engine, delete, func, insert, select, update
from sqlalchemy.engine import Engine

from study_api.chinese_practice import ChinesePoemDraft
from study_api.curriculum_limits import MAX_DOCUMENT_BYTES
from study_api.database import database_url
from study_api.domain.curriculum_knowledge import (
    CHINESE_CURRICULUM_BOOK_ANALYSIS_SCHEMA,
    CHINESE_CURRICULUM_BOOK_PROMPT,
    CHINESE_CURRICULUM_PAGE_ANALYSIS_SCHEMA,
    CHINESE_CURRICULUM_PAGE_PROMPT,
    CURRICULUM_BOOK_ANALYSIS_SCHEMA,
    CURRICULUM_BOOK_PROMPT,
    CURRICULUM_PAGE_ANALYSIS_SCHEMA,
    CURRICULUM_PAGE_PROMPT,
    ChineseProviderBookAnalysis,
    ChineseProviderPageAnalysis,
    CurriculumChapterSummary,
    CurriculumKnowledgeExercise,
    CurriculumKnowledgeMap,
    CurriculumKnowledgePoint,
    CurriculumPageAsset,
    KnowledgeMapStatus,
    ProviderBookAnalysis,
    ProviderPageAnalysis,
)
from study_api.domain.models import Subject
from study_api.material_parser import RENDERER_VERSION, iter_rendered_pdf_pages
from study_api.newapi_provider import (
    CurriculumProviderPage,
    NewApiConfig,
    NewApiProviderError,
    NewApiVisionProvider,
    ProviderCallMetrics,
)
from study_api.object_storage import (
    ObjectStorageConfig,
    ObjectStorageError,
    S3ObjectStorage,
)


@dataclass(frozen=True)
class StoredCurriculumPageAsset:
    metadata: CurriculumPageAsset
    object_key: str


class CurriculumKnowledgeRepository(Protocol):
    def enqueue(
        self, household_id: UUID, child_id: UUID, material_id: UUID, snapshot_id: UUID
    ) -> CurriculumKnowledgeMap: ...

    def get_map(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID
    ) -> CurriculumKnowledgeMap | None: ...

    def list_approved_points(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID | None = None
    ) -> list[CurriculumKnowledgePoint]: ...

    def approve(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID
    ) -> CurriculumKnowledgeMap: ...

    def list_chinese_poems(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID
    ) -> tuple[ChinesePoemDraft, ...]: ...

    def get_page_asset(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID, page_number: int
    ) -> StoredCurriculumPageAsset | None: ...

    def list_page_assets(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID
    ) -> list[StoredCurriculumPageAsset]: ...

    def clone_approved_public_map(
        self,
        source_snapshot_id: UUID,
        target_material_id: UUID,
        target_snapshot_id: UUID,
        target_household_id: UUID,
        target_child_id: UUID,
    ) -> CurriculumKnowledgeMap: ...

    def has_other_asset_reference(self, object_key: str, snapshot_id: UUID) -> bool: ...

    def close(self) -> None: ...


class InMemoryCurriculumKnowledgeRepository:
    """Small injectable repository used by API tests; production work is PostgreSQL."""

    def __init__(self) -> None:
        self._maps: dict[UUID, CurriculumKnowledgeMap] = {}
        self._assets: dict[tuple[UUID, int], StoredCurriculumPageAsset] = {}

    def enqueue(
        self, household_id: UUID, child_id: UUID, material_id: UUID, snapshot_id: UUID
    ) -> CurriculumKnowledgeMap:
        current = self._maps.get(snapshot_id)
        if current is not None and current.status is KnowledgeMapStatus.APPROVED:
            raise ValueError("approved curriculum knowledge cannot be overwritten")
        now = datetime.now(UTC)
        value = CurriculumKnowledgeMap(
            id=current.id if current else uuid4(),
            household_id=household_id,
            child_id=child_id,
            material_id=material_id,
            snapshot_id=snapshot_id,
            status=KnowledgeMapStatus.QUEUED,
            attempt=(current.attempt if current else 0),
            page_count=(current.page_count if current else 0),
            analyzed_page_count=0,
            schema_version=CURRICULUM_BOOK_ANALYSIS_SCHEMA,
            prompt_version=CURRICULUM_BOOK_PROMPT,
            created_at=current.created_at if current else now,
            updated_at=now,
        )
        self._maps[snapshot_id] = value
        return value

    def get_map(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID
    ) -> CurriculumKnowledgeMap | None:
        value = self._maps.get(snapshot_id)
        if value is None or value.household_id != household_id or value.child_id != child_id:
            return None
        return value

    def list_approved_points(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID | None = None
    ) -> list[CurriculumKnowledgePoint]:
        values: list[CurriculumKnowledgePoint] = []
        for knowledge_map in self._maps.values():
            if (
                knowledge_map.household_id == household_id
                and knowledge_map.child_id == child_id
                and knowledge_map.status is KnowledgeMapStatus.APPROVED
                and (snapshot_id is None or knowledge_map.snapshot_id == snapshot_id)
            ):
                values.extend(knowledge_map.knowledge_points)
        return sorted(values, key=lambda point: (point.order_index, point.title))

    def approve(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID
    ) -> CurriculumKnowledgeMap:
        value = self.get_map(household_id, child_id, snapshot_id)
        if value is None:
            raise LookupError
        if value.status not in {
            KnowledgeMapStatus.NEEDS_REVIEW,
            KnowledgeMapStatus.APPROVED,
        }:
            raise ValueError("curriculum knowledge is not ready for review")
        now = datetime.now(UTC)
        approved_points = tuple(
            point.model_copy(update={"status": "approved", "updated_at": now})
            for point in value.knowledge_points
        )
        approved = value.model_copy(
            update={
                "status": KnowledgeMapStatus.APPROVED,
                "reviewed_at": value.reviewed_at or now,
                "updated_at": now,
                "knowledge_points": approved_points,
            }
        )
        self._maps[snapshot_id] = approved
        return approved

    def list_chinese_poems(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID
    ) -> tuple[ChinesePoemDraft, ...]:
        # API tests can inject poem drafts through the Chinese repository; the
        # production repository reads private persisted page analyses below.
        del household_id, child_id, snapshot_id
        return ()

    def get_page_asset(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID, page_number: int
    ) -> StoredCurriculumPageAsset | None:
        asset = self._assets.get((snapshot_id, page_number))
        if (
            asset is None
            or asset.metadata.household_id != household_id
            or asset.metadata.child_id != child_id
        ):
            return None
        return asset

    def list_page_assets(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID
    ) -> list[StoredCurriculumPageAsset]:
        return [
            asset
            for (stored_snapshot_id, _), asset in self._assets.items()
            if stored_snapshot_id == snapshot_id
            and asset.metadata.household_id == household_id
            and asset.metadata.child_id == child_id
        ]

    def save_for_testing(self, knowledge_map: CurriculumKnowledgeMap) -> None:
        self._maps[knowledge_map.snapshot_id] = knowledge_map

    def save_asset_for_testing(self, asset: StoredCurriculumPageAsset) -> None:
        self._assets[(asset.metadata.snapshot_id, asset.metadata.page_number)] = asset

    def clone_approved_public_map(
        self,
        source_snapshot_id: UUID,
        target_material_id: UUID,
        target_snapshot_id: UUID,
        target_household_id: UUID,
        target_child_id: UUID,
    ) -> CurriculumKnowledgeMap:
        source = self._maps.get(source_snapshot_id)
        if source is None or source.status is not KnowledgeMapStatus.APPROVED:
            raise LookupError
        now = datetime.now(UTC)
        points = tuple(
            point.model_copy(
                update={
                    "id": uuid4(),
                    "household_id": target_household_id,
                    "child_id": target_child_id,
                    "material_id": target_material_id,
                    "snapshot_id": target_snapshot_id,
                    "knowledge_map_id": uuid4(),
                    "status": "draft",
                    "created_at": now,
                    "updated_at": now,
                }
            )
            for point in source.knowledge_points
        )
        # The map id must be consistent with every copied point.
        map_id = points[0].knowledge_map_id if points else uuid4()
        points = tuple(point.model_copy(update={"knowledge_map_id": map_id}) for point in points)
        target = source.model_copy(
            update={
                "id": map_id,
                "household_id": target_household_id,
                "child_id": target_child_id,
                "material_id": target_material_id,
                "snapshot_id": target_snapshot_id,
                "status": KnowledgeMapStatus.NEEDS_REVIEW,
                "reviewed_at": None,
                "created_at": now,
                "updated_at": now,
                "knowledge_points": points,
            }
        )
        self._maps[target_snapshot_id] = target
        for (stored_snapshot_id, page), asset in list(self._assets.items()):
            if stored_snapshot_id != source_snapshot_id:
                continue
            metadata = asset.metadata.model_copy(
                update={
                    "id": uuid4(),
                    "household_id": target_household_id,
                    "child_id": target_child_id,
                    "material_id": target_material_id,
                    "snapshot_id": target_snapshot_id,
                    "created_at": now,
                }
            )
            self._assets[(target_snapshot_id, page)] = StoredCurriculumPageAsset(
                metadata=metadata, object_key=asset.object_key
            )
        return target

    def has_other_asset_reference(self, object_key: str, snapshot_id: UUID) -> bool:
        return any(
            stored_snapshot_id != snapshot_id and asset.object_key == object_key
            for (stored_snapshot_id, _), asset in self._assets.items()
        )

    def close(self) -> None:
        return None


@dataclass(frozen=True)
class CurriculumAnalysisJob:
    id: UUID
    household_id: UUID
    child_id: UUID
    material_id: UUID
    snapshot_id: UUID
    object_key: str
    subject: Subject
    attempt: int


class CurriculumBookReferenceError(ValueError):
    """The consolidated book map points outside the validated page evidence."""


def _page_schema(subject: Subject) -> str:
    return (
        CHINESE_CURRICULUM_PAGE_ANALYSIS_SCHEMA
        if subject is Subject.CHINESE
        else CURRICULUM_PAGE_ANALYSIS_SCHEMA
    )


def _book_schema(subject: Subject) -> str:
    return (
        CHINESE_CURRICULUM_BOOK_ANALYSIS_SCHEMA
        if subject is Subject.CHINESE
        else CURRICULUM_BOOK_ANALYSIS_SCHEMA
    )


def _page_prompt(subject: Subject) -> str:
    return CHINESE_CURRICULUM_PAGE_PROMPT if subject is Subject.CHINESE else CURRICULUM_PAGE_PROMPT


def _book_prompt(subject: Subject) -> str:
    return CHINESE_CURRICULUM_BOOK_PROMPT if subject is Subject.CHINESE else CURRICULUM_BOOK_PROMPT


class PostgresCurriculumKnowledgeRepository:
    def __init__(self, url: str | None = None) -> None:
        self._engine = create_engine(url or database_url(), pool_pre_ping=True)
        metadata = MetaData()
        self._maps = Table("curriculum_knowledge_maps", metadata, autoload_with=self._engine)
        self._pages = Table("curriculum_page_analyses", metadata, autoload_with=self._engine)
        self._points = Table("curriculum_knowledge_points", metadata, autoload_with=self._engine)
        self._assets = Table("curriculum_page_assets", metadata, autoload_with=self._engine)
        self._materials = Table("learning_materials", metadata, autoload_with=self._engine)
        self._chunks = Table("curriculum_chunks", metadata, autoload_with=self._engine)

    @property
    def engine(self) -> Engine:
        return self._engine

    def close(self) -> None:
        self._engine.dispose()

    def list_chinese_poems(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID
    ) -> tuple[ChinesePoemDraft, ...]:
        statement = (
            select(self._pages.c.page_number, self._pages.c.knowledge_observations)
            .join(self._maps, self._maps.c.id == self._pages.c.knowledge_map_id)
            .where(
                self._pages.c.household_id == household_id,
                self._pages.c.child_id == child_id,
                self._pages.c.snapshot_id == snapshot_id,
                self._maps.c.status == KnowledgeMapStatus.APPROVED.value,
            )
            .order_by(self._pages.c.page_number)
        )
        poems: list[ChinesePoemDraft] = []
        with self._engine.connect() as connection:
            for row in connection.execute(statement).mappings():
                for observation in row["knowledge_observations"]:
                    if not isinstance(observation, dict):
                        continue
                    for passage in observation.get("passages", []):
                        if not isinstance(passage, dict) or passage.get("kind") != "poem":
                            continue
                        lines = passage.get("lines", [])
                        if not isinstance(lines, list):
                            continue
                        try:
                            poems.append(
                                ChinesePoemDraft(
                                    title=passage.get("title") or "教材古诗",
                                    page_number=row["page_number"],
                                    lines=tuple(str(line) for line in lines),
                                )
                            )
                        except ValueError:
                            continue
        return tuple(poems)

    def enqueue(
        self, household_id: UUID, child_id: UUID, material_id: UUID, snapshot_id: UUID
    ) -> CurriculumKnowledgeMap:
        now = datetime.now(UTC)
        with self._engine.begin() as connection:
            existing = (
                connection.execute(
                    select(self._maps).where(
                        self._maps.c.snapshot_id == snapshot_id,
                        self._maps.c.household_id == household_id,
                        self._maps.c.child_id == child_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            page_count = int(
                connection.execute(
                    select(func.count())
                    .select_from(self._chunks)
                    .where(self._chunks.c.snapshot_id == snapshot_id)
                ).scalar_one()
                or 0
            )
            if existing is not None:
                if existing["status"] == KnowledgeMapStatus.APPROVED.value:
                    raise ValueError("approved curriculum knowledge cannot be overwritten")
                connection.execute(
                    update(self._maps)
                    .where(self._maps.c.id == existing["id"])
                    .values(
                        status=KnowledgeMapStatus.QUEUED.value,
                        analyzed_page_count=0,
                        error_code=None,
                        updated_at=now,
                    )
                )
                map_id = existing["id"]
            else:
                map_id = uuid4()
                connection.execute(
                    insert(self._maps).values(
                        id=map_id,
                        household_id=household_id,
                        child_id=child_id,
                        material_id=material_id,
                        snapshot_id=snapshot_id,
                        status=KnowledgeMapStatus.QUEUED.value,
                        attempt=0,
                        book_summary=None,
                        chapters=[],
                        page_count=page_count,
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
        value = self.get_map(household_id, child_id, snapshot_id)
        if value is None:  # pragma: no cover - transaction invariant
            raise RuntimeError("curriculum knowledge map was not created")
        return value

    def claim_next(self) -> CurriculumAnalysisJob | None:
        with self._engine.begin() as connection:
            row = (
                connection.execute(
                    select(self._maps)
                    .where(self._maps.c.status == KnowledgeMapStatus.QUEUED.value)
                    .order_by(self._maps.c.created_at, self._maps.c.id)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            material = connection.execute(
                select(self._materials.c.object_key, self._materials.c.subject).where(
                    self._materials.c.id == row["material_id"]
                )
            ).one_or_none()
            if material is None or not isinstance(material.object_key, str):
                self._mark_failed(connection, row["id"], "material_object_missing")
                return None
            try:
                subject = Subject(str(material.subject))
            except ValueError:
                self._mark_failed(connection, row["id"], "material_subject_invalid")
                return None
            now = datetime.now(UTC)
            attempt = int(row["attempt"]) + 1
            connection.execute(
                update(self._maps)
                .where(self._maps.c.id == row["id"])
                .values(
                    status=KnowledgeMapStatus.ANALYZING.value,
                    attempt=attempt,
                    error_code=None,
                    updated_at=now,
                )
            )
            return CurriculumAnalysisJob(
                id=row["id"],
                household_id=row["household_id"],
                child_id=row["child_id"],
                material_id=row["material_id"],
                snapshot_id=row["snapshot_id"],
                object_key=material.object_key,
                subject=subject,
                attempt=attempt,
            )

    def page_texts(self, job: CurriculumAnalysisJob) -> dict[int, str]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                select(self._chunks.c.page_number, self._chunks.c.text).where(
                    self._chunks.c.snapshot_id == job.snapshot_id
                )
            ).all()
        return {int(row.page_number): str(row.text) for row in rows}

    def save_page_asset(
        self,
        job: CurriculumAnalysisJob,
        *,
        page_number: int,
        object_key: str,
        byte_size: int,
        image_sha256: str,
        width: int,
        height: int,
    ) -> None:
        now = datetime.now(UTC)
        with self._engine.begin() as connection:
            existing = connection.execute(
                select(self._assets.c.id).where(
                    self._assets.c.snapshot_id == job.snapshot_id,
                    self._assets.c.page_number == page_number,
                )
            ).scalar_one_or_none()
            values = {
                "household_id": job.household_id,
                "child_id": job.child_id,
                "material_id": job.material_id,
                "snapshot_id": job.snapshot_id,
                "page_number": page_number,
                "media_type": "image/jpeg",
                "byte_size": byte_size,
                "image_sha256": image_sha256,
                "width": width,
                "height": height,
                "object_key": object_key,
                "renderer_version": RENDERER_VERSION,
                "created_at": now,
            }
            if existing is None:
                connection.execute(insert(self._assets).values(id=uuid4(), **values))
            else:
                connection.execute(
                    update(self._assets).where(self._assets.c.id == existing).values(**values)
                )

    def complete(
        self,
        job: CurriculumAnalysisJob,
        *,
        page_analyses: tuple[ProviderPageAnalysis | ChineseProviderPageAnalysis, ...],
        book: ProviderBookAnalysis | ChineseProviderBookAnalysis,
        exercises_by_key: dict[str, CurriculumKnowledgeExercise],
        provider: str,
        model: str,
        input_fingerprint: str,
        output_fingerprint: str,
        latency_ms: int,
        input_tokens: int | None,
        output_tokens: int | None,
        cost_cents: float | None,
    ) -> None:
        now = datetime.now(UTC)
        point_rows = _resolve_knowledge_points(job, book, exercises_by_key, now)
        chapters = [
            {
                "title": chapter.title,
                "start_page": chapter.start_page,
                "end_page": chapter.end_page,
                "summary": chapter.summary,
                "knowledge_keys": [point.knowledge_key for point in chapter.knowledge_points],
            }
            for chapter in book.chapters
        ]
        with self._engine.begin() as connection:
            connection.execute(delete(self._pages).where(self._pages.c.knowledge_map_id == job.id))
            connection.execute(
                delete(self._points).where(self._points.c.knowledge_map_id == job.id)
            )
            for page in page_analyses:
                page_json = page.model_dump(mode="json")
                page_fingerprint = sha256(str(page_json).encode("utf-8")).hexdigest()
                connection.execute(
                    insert(self._pages).values(
                        id=uuid4(),
                        household_id=job.household_id,
                        child_id=job.child_id,
                        material_id=job.material_id,
                        snapshot_id=job.snapshot_id,
                        knowledge_map_id=job.id,
                        page_number=page.page_number,
                        chapter_title=page.chapter_title,
                        section_title=page.section_title,
                        summary=page.summary,
                        knowledge_observations=[
                            observation.model_dump(mode="json")
                            for observation in page.knowledge_observations
                        ]
                        + (
                            [{"passages": [item.model_dump(mode="json") for item in page.passages]}]
                            if isinstance(page, ChineseProviderPageAnalysis)
                            else []
                        ),
                        confidence=page.confidence,
                        provider=provider,
                        model=model,
                        schema_version=_page_schema(job.subject),
                        prompt_version=_page_prompt(job.subject),
                        input_fingerprint=input_fingerprint,
                        output_fingerprint=page_fingerprint,
                        latency_ms=None,
                        input_tokens=None,
                        output_tokens=None,
                        cost_cents=None,
                        created_at=now,
                    )
                )
            for point in point_rows:
                values = point.model_dump(
                    exclude={"exercises", "learning_objectives", "prerequisites", "page_numbers"}
                )
                values["learning_objectives"] = list(point.learning_objectives)
                values["prerequisites"] = list(point.prerequisites)
                values["page_numbers"] = list(point.page_numbers)
                values["exercises"] = [
                    exercise.model_dump(mode="json") for exercise in point.exercises
                ]
                connection.execute(insert(self._points).values(**values))
            connection.execute(
                update(self._maps)
                .where(self._maps.c.id == job.id)
                .values(
                    status=KnowledgeMapStatus.NEEDS_REVIEW.value,
                    book_summary=book.book_summary,
                    chapters=chapters,
                    page_count=len(page_analyses),
                    analyzed_page_count=len(page_analyses),
                    provider=provider,
                    model=model,
                    schema_version=_book_schema(job.subject),
                    prompt_version=_book_prompt(job.subject),
                    input_fingerprint=input_fingerprint,
                    output_fingerprint=output_fingerprint,
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_cents=cost_cents,
                    error_code=None,
                    updated_at=now,
                )
            )

    def fail(self, job: CurriculumAnalysisJob, code: str) -> None:
        with self._engine.begin() as connection:
            self._mark_failed(connection, job.id, code)

    def _mark_failed(self, connection: Any, map_id: UUID, code: str) -> None:
        connection.execute(
            update(self._maps)
            .where(self._maps.c.id == map_id)
            .values(
                status=KnowledgeMapStatus.FAILED.value,
                error_code=code[:80],
                updated_at=datetime.now(UTC),
            )
        )

    def get_map(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID
    ) -> CurriculumKnowledgeMap | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    select(self._maps).where(
                        self._maps.c.household_id == household_id,
                        self._maps.c.child_id == child_id,
                        self._maps.c.snapshot_id == snapshot_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            point_rows = (
                connection.execute(
                    select(self._points)
                    .where(self._points.c.knowledge_map_id == row["id"])
                    .order_by(self._points.c.order_index, self._points.c.id)
                )
                .mappings()
                .all()
            )
        return _read_map(dict(row), [_read_point(dict(point)) for point in point_rows])

    def list_approved_points(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID | None = None
    ) -> list[CurriculumKnowledgePoint]:
        statement = (
            select(self._points)
            .where(
                self._points.c.household_id == household_id,
                self._points.c.child_id == child_id,
                self._points.c.status == "approved",
            )
            .order_by(self._points.c.order_index, self._points.c.id)
        )
        if snapshot_id is not None:
            statement = statement.where(self._points.c.snapshot_id == snapshot_id)
        with self._engine.connect() as connection:
            return [
                _read_point(dict(row)) for row in connection.execute(statement).mappings().all()
            ]

    def approve(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID
    ) -> CurriculumKnowledgeMap:
        now = datetime.now(UTC)
        with self._engine.begin() as connection:
            row = (
                connection.execute(
                    select(self._maps)
                    .where(
                        self._maps.c.household_id == household_id,
                        self._maps.c.child_id == child_id,
                        self._maps.c.snapshot_id == snapshot_id,
                    )
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise LookupError
            if row["status"] not in {
                KnowledgeMapStatus.NEEDS_REVIEW.value,
                KnowledgeMapStatus.APPROVED.value,
            }:
                raise ValueError("curriculum knowledge is not ready for review")
            connection.execute(
                update(self._maps)
                .where(self._maps.c.id == row["id"])
                .values(
                    status=KnowledgeMapStatus.APPROVED.value,
                    reviewed_at=row["reviewed_at"] or now,
                    updated_at=now,
                )
            )
            connection.execute(
                update(self._points)
                .where(self._points.c.knowledge_map_id == row["id"])
                .values(status="approved", updated_at=now)
            )
        value = self.get_map(household_id, child_id, snapshot_id)
        if value is None:  # pragma: no cover - transaction invariant
            raise RuntimeError("approved curriculum knowledge disappeared")
        return value

    def get_page_asset(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID, page_number: int
    ) -> StoredCurriculumPageAsset | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    select(self._assets).where(
                        self._assets.c.household_id == household_id,
                        self._assets.c.child_id == child_id,
                        self._assets.c.snapshot_id == snapshot_id,
                        self._assets.c.page_number == page_number,
                    )
                )
                .mappings()
                .one_or_none()
            )
        return _read_asset(dict(row)) if row is not None else None

    def list_page_assets(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID
    ) -> list[StoredCurriculumPageAsset]:
        with self._engine.connect() as connection:
            rows = (
                connection.execute(
                    select(self._assets)
                    .where(
                        self._assets.c.household_id == household_id,
                        self._assets.c.child_id == child_id,
                        self._assets.c.snapshot_id == snapshot_id,
                    )
                    .order_by(self._assets.c.page_number)
                )
                .mappings()
                .all()
            )
            return [_read_asset(dict(row)) for row in rows]

    def clone_approved_public_map(
        self,
        source_snapshot_id: UUID,
        target_material_id: UUID,
        target_snapshot_id: UUID,
        target_household_id: UUID,
        target_child_id: UUID,
    ) -> CurriculumKnowledgeMap:
        """Copy approved public derived facts into a local review draft.

        This never exposes source tenant IDs in a response. The copied map is
        deliberately `needs_review`: each family independently approves it.
        """

        now = datetime.now(UTC)
        with self._engine.begin() as connection:
            source_map = (
                connection.execute(
                    select(self._maps)
                    .where(self._maps.c.snapshot_id == source_snapshot_id)
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if source_map is None or source_map["status"] != KnowledgeMapStatus.APPROVED.value:
                raise LookupError
            map_id = uuid4()
            map_values = dict(source_map)
            map_values.update(
                id=map_id,
                household_id=target_household_id,
                child_id=target_child_id,
                material_id=target_material_id,
                snapshot_id=target_snapshot_id,
                status=KnowledgeMapStatus.NEEDS_REVIEW.value,
                reviewed_at=None,
                created_at=now,
                updated_at=now,
            )
            connection.execute(insert(self._maps).values(**map_values))
            for table in (self._pages, self._points):
                rows = (
                    connection.execute(
                        select(table).where(table.c.knowledge_map_id == source_map["id"])
                    )
                    .mappings()
                    .all()
                )
                for row in rows:
                    values = dict(row)
                    values.update(
                        id=uuid4(),
                        household_id=target_household_id,
                        child_id=target_child_id,
                        material_id=target_material_id,
                        snapshot_id=target_snapshot_id,
                        knowledge_map_id=map_id,
                        created_at=now,
                    )
                    if table is self._points:
                        values.update(status="draft", updated_at=now)
                    connection.execute(insert(table).values(**values))
            assets = (
                connection.execute(
                    select(self._assets).where(self._assets.c.snapshot_id == source_snapshot_id)
                )
                .mappings()
                .all()
            )
            for row in assets:
                values = dict(row)
                values.update(
                    id=uuid4(),
                    household_id=target_household_id,
                    child_id=target_child_id,
                    material_id=target_material_id,
                    snapshot_id=target_snapshot_id,
                    created_at=now,
                )
                connection.execute(insert(self._assets).values(**values))
        value = self.get_map(target_household_id, target_child_id, target_snapshot_id)
        if value is None:  # pragma: no cover - transactional invariant
            raise RuntimeError("copied curriculum map was not saved")
        return value

    def has_other_asset_reference(self, object_key: str, snapshot_id: UUID) -> bool:
        with self._engine.connect() as connection:
            return (
                connection.execute(
                    select(self._assets.c.id)
                    .where(
                        self._assets.c.object_key == object_key,
                        self._assets.c.snapshot_id != snapshot_id,
                    )
                    .limit(1)
                ).scalar_one_or_none()
                is not None
            )


def _read_asset(row: dict[str, Any]) -> StoredCurriculumPageAsset:
    object_key = str(row.pop("object_key"))
    return StoredCurriculumPageAsset(
        metadata=CurriculumPageAsset.model_validate(row),
        object_key=object_key,
    )


def _read_point(row: dict[str, Any]) -> CurriculumKnowledgePoint:
    row["learning_objectives"] = tuple(row.get("learning_objectives") or ())
    row["prerequisites"] = tuple(row.get("prerequisites") or ())
    row["page_numbers"] = tuple(int(page) for page in row.get("page_numbers") or ())
    row["exercises"] = tuple(
        CurriculumKnowledgeExercise.model_validate(item) for item in row.get("exercises") or ()
    )
    return CurriculumKnowledgePoint.model_validate(row)


def _read_map(
    row: dict[str, Any], points: list[CurriculumKnowledgePoint]
) -> CurriculumKnowledgeMap:
    row["chapters"] = tuple(
        CurriculumChapterSummary.model_validate(chapter) for chapter in row.get("chapters") or ()
    )
    row["knowledge_points"] = tuple(points)
    for private_field in (
        "input_fingerprint",
        "output_fingerprint",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "cost_cents",
    ):
        row.pop(private_field, None)
    return CurriculumKnowledgeMap.model_validate(row)


def _resolve_knowledge_points(
    job: CurriculumAnalysisJob,
    book: ProviderBookAnalysis | ChineseProviderBookAnalysis,
    exercises_by_key: dict[str, CurriculumKnowledgeExercise],
    now: datetime,
) -> tuple[CurriculumKnowledgePoint, ...]:
    seen_keys: set[str] = set()
    rows: list[CurriculumKnowledgePoint] = []
    for chapter in book.chapters:
        for point in chapter.knowledge_points:
            if point.knowledge_key in seen_keys:
                raise ValueError("book analysis repeats a knowledge key")
            seen_keys.add(point.knowledge_key)
            pages = tuple(dict.fromkeys(point.page_numbers))
            if any(page < chapter.start_page or page > chapter.end_page for page in pages):
                raise ValueError("knowledge point references a page outside its chapter")
            try:
                exercises = tuple(exercises_by_key[key] for key in point.exercise_keys)
            except KeyError as error:
                raise ValueError("book analysis invented an exercise source") from error
            rows.append(
                CurriculumKnowledgePoint(
                    id=uuid4(),
                    household_id=job.household_id,
                    child_id=job.child_id,
                    material_id=job.material_id,
                    snapshot_id=job.snapshot_id,
                    knowledge_map_id=job.id,
                    knowledge_key=point.knowledge_key,
                    order_index=len(rows),
                    chapter_title=chapter.title,
                    section_title=point.section_title,
                    title=point.title,
                    summary=point.summary,
                    learning_objectives=point.learning_objectives,
                    prerequisites=point.prerequisites,
                    page_numbers=pages,
                    exercises=exercises,
                    confidence=point.confidence,
                    status="draft",
                    created_at=now,
                    updated_at=now,
                )
            )
    if not rows:
        raise ValueError("book analysis returned no knowledge points")
    return tuple(rows)


def _page_payloads(
    analyses: tuple[ProviderPageAnalysis, ...],
) -> tuple[tuple[dict[str, Any], ...], dict[str, CurriculumKnowledgeExercise]]:
    payloads: list[dict[str, Any]] = []
    exercises: dict[str, CurriculumKnowledgeExercise] = {}
    for page in analyses:
        observations: list[dict[str, Any]] = []
        for observation_index, observation in enumerate(page.knowledge_observations):
            exercise_summaries: list[dict[str, Any]] = []
            for exercise_index, exercise in enumerate(observation.exercises):
                source_key = (
                    f"page:{page.page_number}:observation:{observation_index}:"
                    f"exercise:{exercise_index}"
                )
                exercises[source_key] = CurriculumKnowledgeExercise(
                    source_key=source_key,
                    page_number=page.page_number,
                    **exercise.model_dump(),
                )
                exercise_summaries.append(
                    {
                        "exercise_key": source_key,
                        "question_text": exercise.question_text,
                        "visual_description": exercise.visual_description,
                        "requires_visual_context": exercise.requires_visual_context,
                    }
                )
            observations.append(
                {
                    "title": observation.title,
                    "summary": observation.summary,
                    "learning_objectives": observation.learning_objectives,
                    "prerequisites": observation.prerequisites,
                    "exercises": exercise_summaries,
                    "confidence": observation.confidence,
                }
            )
        page_payload = {
            "page_number": page.page_number,
            "chapter_title": page.chapter_title,
            "section_title": page.section_title,
            "summary": page.summary,
            "knowledge_observations": observations,
            "confidence": page.confidence,
        }
        payloads.append(page_payload)
    return tuple(payloads), exercises


def _validate_book_coverage(
    book: ProviderBookAnalysis | ChineseProviderBookAnalysis, known_pages: set[int]
) -> None:
    for chapter in book.chapters:
        if any(page not in known_pages for page in range(chapter.start_page, chapter.end_page + 1)):
            raise CurriculumBookReferenceError("book analysis chapter references an unknown page")
        for point in chapter.knowledge_points:
            if any(page not in known_pages for page in point.page_numbers):
                raise CurriculumBookReferenceError("book analysis references an unknown page")


def run_once(
    repository: PostgresCurriculumKnowledgeRepository,
    storage: S3ObjectStorage,
    provider: NewApiVisionProvider,
) -> bool:
    job = repository.claim_next()
    if job is None:
        return False
    started = time.monotonic()
    try:
        document = storage.read_document(job.object_key, MAX_DOCUMENT_BYTES)
        page_texts = repository.page_texts(job)
        analyses: list[ProviderPageAnalysis | ChineseProviderPageAnalysis] = []
        batch: list[CurriculumProviderPage] = []
        image_hashes: list[str] = []
        provider_metrics: list[ProviderCallMetrics] = []
        for rendered in iter_rendered_pdf_pages(document):
            object_key = (
                f"curriculum-previews/{job.household_id}/{job.child_id}/"
                f"{job.snapshot_id}/{rendered.page_number}-{rendered.image_sha256[:16]}.jpg"
            )
            storage.write_curriculum_preview(object_key, rendered.data)
            repository.save_page_asset(
                job,
                page_number=rendered.page_number,
                object_key=object_key,
                byte_size=len(rendered.data),
                image_sha256=rendered.image_sha256,
                width=rendered.width,
                height=rendered.height,
            )
            image_hashes.append(rendered.image_sha256)
            batch.append(
                CurriculumProviderPage(
                    page_number=rendered.page_number,
                    extracted_text=page_texts.get(rendered.page_number, ""),
                    image_bytes=rendered.data,
                )
            )
            if len(batch) == 4:
                analyses.extend(
                    provider.analyze_curriculum_pages(tuple(batch), subject=job.subject)
                )
                if provider.last_call_metrics is not None:
                    provider_metrics.append(provider.last_call_metrics)
                batch.clear()
        if batch:
            analyses.extend(provider.analyze_curriculum_pages(tuple(batch), subject=job.subject))
            if provider.last_call_metrics is not None:
                provider_metrics.append(provider.last_call_metrics)
        if not analyses:
            raise ValueError("curriculum analysis rendered no pages")
        page_payloads, exercises = _page_payloads(tuple(analyses))
        book = provider.consolidate_curriculum_book(
            page_observations=page_payloads, subject=job.subject
        )
        if provider.last_call_metrics is not None:
            provider_metrics.append(provider.last_call_metrics)
        known_pages = {page.page_number for page in analyses}
        _validate_book_coverage(book, known_pages)
        input_fingerprint = sha256(
            f"{sha256(document).hexdigest()}:{':'.join(image_hashes)}".encode()
        ).hexdigest()
        output_fingerprint = sha256(book.model_dump_json().encode()).hexdigest()
        repository.complete(
            job,
            page_analyses=tuple(analyses),
            book=book,
            exercises_by_key=exercises,
            provider="newapi",
            model=provider._config.vision_model,
            input_fingerprint=input_fingerprint,
            output_fingerprint=output_fingerprint,
            latency_ms=int((time.monotonic() - started) * 1000),
            input_tokens=_sum_optional_int_metrics(provider_metrics, "input_tokens"),
            output_tokens=_sum_optional_int_metrics(provider_metrics, "output_tokens"),
            cost_cents=_sum_optional_cost(provider_metrics),
        )
    except NewApiProviderError as error:
        repository.fail(job, error.code)
    except ObjectStorageError:
        repository.fail(job, "curriculum_storage_unavailable")
    except CurriculumBookReferenceError:
        repository.fail(job, "curriculum_book_reference_invalid")
    except ValueError:
        repository.fail(job, "curriculum_analysis_invalid")
    except Exception:  # noqa: BLE001 - worker persists a stable failure code
        repository.fail(job, "curriculum_analysis_failed")
    return True


def _sum_optional_int_metrics(metrics: list[ProviderCallMetrics], field: str) -> int | None:
    values = [getattr(metric, field) for metric in metrics]
    present = [int(value) for value in values if isinstance(value, int)]
    return sum(present) if present else None


def _sum_optional_cost(metrics: list[ProviderCallMetrics]) -> float | None:
    present = [metric.cost_cents for metric in metrics if metric.cost_cents is not None]
    return round(sum(present), 4) if present else None


def main() -> int:
    config = NewApiConfig.from_environment()
    if not config.enabled:
        if "--watch" not in sys.argv[1:]:
            return 0
        # Compose keeps the worker in the default profile. When NewAPI is
        # deliberately disabled, remain idle without claiming jobs or entering
        # a restart loop; changing the environment still requires a normal
        # container restart.
        while True:
            time.sleep(60)
    repository = PostgresCurriculumKnowledgeRepository()
    storage = S3ObjectStorage(ObjectStorageConfig.from_environment())
    provider = NewApiVisionProvider(config)
    try:
        watch = "--watch" in sys.argv[1:]
        while True:
            processed = run_once(repository, storage, provider)
            if not watch:
                break
            if not processed:
                time.sleep(float(os.environ.get("CURRICULUM_ANALYSIS_POLL_INTERVAL_SECONDS", "2")))
        return 0
    finally:
        repository.close()


if __name__ == "__main__":
    raise SystemExit(main())
