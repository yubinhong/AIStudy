"""Structured, source-bound knowledge extracted from private curriculum PDFs."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

CURRICULUM_PAGE_ANALYSIS_SCHEMA = "curriculum-page-analysis.v1"
CURRICULUM_BOOK_ANALYSIS_SCHEMA = "curriculum-book-analysis.v1"
CURRICULUM_PAGE_PROMPT = "curriculum-page-visual.v5"
CURRICULUM_BOOK_PROMPT = "curriculum-book-consolidation.v5"
CHINESE_CURRICULUM_PAGE_ANALYSIS_SCHEMA = "chinese-curriculum-page-analysis.v2"
CHINESE_CURRICULUM_BOOK_ANALYSIS_SCHEMA = "chinese-curriculum-book-analysis.v2"
CHINESE_CURRICULUM_PAGE_PROMPT = "chinese-curriculum-page-visual.v2"
CHINESE_CURRICULUM_BOOK_PROMPT = "chinese-curriculum-book-consolidation.v2"


class KnowledgeMapStatus(StrEnum):
    QUEUED = "queued"
    ANALYZING = "analyzing"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    FAILED = "failed"


class ProviderExercise(BaseModel):
    """One exact exercise recovered from a page image.

    The model describes visual dependencies separately so a text sentence is never
    presented as a complete problem when the page diagram carries required facts.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    question_text: str = Field(min_length=1, max_length=2_000)
    visual_description: str | None = Field(default=None, max_length=1_000)
    requires_visual_context: bool
    difficulty: Literal["basic", "medium", "advanced"]
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def require_visual_description(self) -> ProviderExercise:
        if self.requires_visual_context and not self.visual_description:
            raise ValueError("visual_description is required for a visual exercise")
        return self


class ProviderKnowledgeObservation(BaseModel):
    """Sparse, page-local evidence used before whole-book consolidation.

    A single page can introduce or practise a concept without stating a learnable
    objective.  Do not manufacture one merely to satisfy an intermediate schema;
    the final, reviewable book map remains responsible for complete objectives.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=1_000)
    learning_objectives: tuple[str, ...] = Field(default=(), max_length=8)
    prerequisites: tuple[str, ...] = Field(default=(), max_length=8)
    exercises: tuple[ProviderExercise, ...] = Field(default=(), max_length=12)
    confidence: float = Field(ge=0, le=1)


class ProviderPageAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    page_number: int = Field(ge=1, le=400)
    chapter_title: str = Field(min_length=1, max_length=160)
    section_title: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=1_500)
    knowledge_observations: tuple[ProviderKnowledgeObservation, ...] = Field(
        default=(), max_length=12
    )
    confidence: float = Field(ge=0, le=1)


class ProviderPageAnalysisBatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["curriculum-page-analysis.v1"]
    pages: tuple[ProviderPageAnalysis, ...] = Field(min_length=1, max_length=4)


class ChinesePassageEvidence(BaseModel):
    """A page-local, reviewable boundary for Chinese text or recitation material."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str | None = Field(default=None, max_length=160)
    start_marker: str = Field(min_length=1, max_length=160)
    end_marker: str = Field(min_length=1, max_length=160)
    kind: Literal["pinyin", "character", "vocabulary", "passage", "poem", "exercise"]
    confidence: float = Field(ge=0, le=1)


class ChineseProviderPageAnalysis(ProviderPageAnalysis):
    passages: tuple[ChinesePassageEvidence, ...] = Field(default=(), max_length=16)


class ChineseProviderPageAnalysisBatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["chinese-curriculum-page-analysis.v2"]
    pages: tuple[ChineseProviderPageAnalysis, ...] = Field(min_length=1, max_length=4)


class ProviderBookKnowledgePoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    knowledge_key: str = Field(pattern=r"^kp-[a-z0-9-]{1,64}$")
    section_title: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=1_500)
    learning_objectives: tuple[str, ...] = Field(min_length=1, max_length=10)
    prerequisites: tuple[str, ...] = Field(default=(), max_length=10)
    page_numbers: tuple[int, ...] = Field(min_length=1, max_length=80)
    exercise_keys: tuple[str, ...] = Field(default=(), max_length=30)
    confidence: float = Field(ge=0, le=1)


class ProviderBookChapter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(min_length=1, max_length=160)
    start_page: int = Field(ge=1, le=400)
    end_page: int = Field(ge=1, le=400)
    summary: str = Field(min_length=1, max_length=1_500)
    # Covers, contents and unit-divider pages can form a truthful chapter range
    # without introducing a teachable point. Final approval still requires at
    # least one point across the complete book.
    knowledge_points: tuple[ProviderBookKnowledgePoint, ...] = Field(default=(), max_length=40)

    @model_validator(mode="after")
    def validate_page_range(self) -> ProviderBookChapter:
        if self.end_page < self.start_page:
            raise ValueError("chapter page range is reversed")
        return self


class ProviderBookAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["curriculum-book-analysis.v1"]
    book_summary: str = Field(min_length=1, max_length=4_000)
    chapters: tuple[ProviderBookChapter, ...] = Field(min_length=1, max_length=40)


class ChineseProviderBookAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["chinese-curriculum-book-analysis.v2"]
    book_summary: str = Field(min_length=1, max_length=4_000)
    chapters: tuple[ProviderBookChapter, ...] = Field(min_length=1, max_length=40)


class CurriculumKnowledgeExercise(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_key: str = Field(min_length=1, max_length=120)
    page_number: int = Field(ge=1, le=400)
    question_text: str = Field(min_length=1, max_length=2_000)
    visual_description: str | None = Field(default=None, max_length=1_000)
    requires_visual_context: bool
    difficulty: Literal["basic", "medium", "advanced"]
    confidence: float = Field(ge=0, le=1)


class CurriculumKnowledgePoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    household_id: UUID
    child_id: UUID
    material_id: UUID
    snapshot_id: UUID
    knowledge_map_id: UUID
    knowledge_key: str = Field(min_length=1, max_length=80)
    order_index: int = Field(ge=0)
    chapter_title: str = Field(min_length=1, max_length=160)
    section_title: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=1_500)
    learning_objectives: tuple[str, ...]
    prerequisites: tuple[str, ...]
    page_numbers: tuple[int, ...]
    exercises: tuple[CurriculumKnowledgeExercise, ...]
    confidence: float = Field(ge=0, le=1)
    status: Literal["draft", "approved", "rejected"]
    created_at: datetime
    updated_at: datetime


class CurriculumChapterSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str
    start_page: int
    end_page: int
    summary: str
    knowledge_keys: tuple[str, ...] = ()


class CurriculumKnowledgeMap(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    household_id: UUID
    child_id: UUID
    material_id: UUID
    snapshot_id: UUID
    status: KnowledgeMapStatus
    attempt: int = Field(ge=0)
    book_summary: str | None = None
    chapters: tuple[CurriculumChapterSummary, ...] = ()
    page_count: int = Field(ge=0)
    analyzed_page_count: int = Field(ge=0)
    provider: str | None = None
    model: str | None = None
    schema_version: str
    prompt_version: str
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None = None
    knowledge_points: tuple[CurriculumKnowledgePoint, ...] = ()


class CurriculumPageAsset(BaseModel):
    """Public metadata; private MinIO object_key never leaves repository/worker code."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    household_id: UUID
    child_id: UUID
    material_id: UUID
    snapshot_id: UUID
    page_number: int = Field(ge=1)
    media_type: Literal["image/jpeg"]
    byte_size: int = Field(ge=1, le=2_097_152)
    image_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    width: int = Field(ge=1, le=4000)
    height: int = Field(ge=1, le=4000)
    renderer_version: str
    created_at: datetime
