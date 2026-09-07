"""Household-scoped Chinese practice routes."""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from study_api.auth import AuthenticatedPrincipal, get_principal, require_household, require_parent
from study_api.chinese_practice import (
    ChineseAttempt,
    ChineseAttemptRequest,
    ChineseContentItemView,
    ChineseLearningDetail,
    ChinesePracticeRepository,
    ChineseReviewItem,
    ChineseSkill,
    ChineseSkillReport,
    PublishChinesePoemsRequest,
)
from study_api.domain.curriculum_repository import CurriculumRepository
from study_api.domain.models import AccountRole, Subject
from study_api.domain.repository import IdempotencyConflictError, ProfileRepository

router = APIRouter(
    prefix="/households/{household_id}/children/{child_id}/chinese",
    tags=["chinese-practice"],
)
Principal = Annotated[AuthenticatedPrincipal, Depends(get_principal)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]

CHINESE_HISTORY_DEFAULT_WINDOW = timedelta(days=30)
CHINESE_HISTORY_MAX_QUERY_WINDOW = timedelta(days=31)
CHINESE_HISTORY_RETENTION = timedelta(days=180)


def _repository(request: Request) -> ChinesePracticeRepository:
    return request.app.state.chinese_practice_repository


def _profiles(request: Request) -> ProfileRepository:
    return request.app.state.profile_repository


Repository = Annotated[ChinesePracticeRepository, Depends(_repository)]
Profiles = Annotated[ProfileRepository, Depends(_profiles)]


def _curriculum(request: Request) -> CurriculumRepository:
    return request.app.state.curriculum_repository


Curriculum = Annotated[CurriculumRepository, Depends(_curriculum)]


def _authorize(
    household_id: UUID,
    child_id: UUID,
    principal: AuthenticatedPrincipal,
    profiles: ProfileRepository,
) -> int:
    role = require_household(principal, household_id)
    child = profiles.get_child(household_id, child_id)
    if child is None:
        raise HTTPException(status_code=404, detail="resource not found")
    if role is AccountRole.CHILD:
        if principal.child_id != child_id:
            raise HTTPException(status_code=404, detail="resource not found")
    elif child.owner_account_id != principal.account_id:
        raise HTTPException(status_code=404, detail="resource not found")
    if Subject.CHINESE not in child.subjects:
        raise HTTPException(status_code=409, detail="chinese subject is not enabled")
    return child.grade


@router.get("/content", response_model=list[ChineseContentItemView])
def list_content(
    household_id: UUID,
    child_id: UUID,
    principal: Principal,
    repository: Repository,
    profiles: Profiles,
    skill: Annotated[ChineseSkill | None, Query()] = None,
) -> list[ChineseContentItemView]:
    grade = _authorize(household_id, child_id, principal, profiles)
    return [
        ChineseContentItemView.from_item(item)
        for item in repository.list_content(grade, skill, household_id, child_id)
    ]


def _aware_utc(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise HTTPException(status_code=422, detail=f"{name} must include a timezone")
    return value.astimezone(UTC)


@router.get(
    "/learning-details",
    response_model=list[ChineseLearningDetail],
    operation_id="getChineseLearningDetails",
)
def list_learning_details(
    household_id: UUID,
    child_id: UUID,
    principal: Principal,
    repository: Repository,
    profiles: Profiles,
    from_at: Annotated[datetime | None, Query()] = None,
    to_at: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> tuple[ChineseLearningDetail, ...]:
    _authorize(household_id, child_id, principal, profiles)
    require_parent(principal.role)
    now = datetime.now(UTC)
    effective_to = _aware_utc(to_at, "to_at") if to_at is not None else now
    effective_from = (
        _aware_utc(from_at, "from_at")
        if from_at is not None
        else effective_to - CHINESE_HISTORY_DEFAULT_WINDOW
    )
    if effective_from >= effective_to:
        raise HTTPException(status_code=422, detail="from_at must be before to_at")
    if effective_to - effective_from > CHINESE_HISTORY_MAX_QUERY_WINDOW:
        raise HTTPException(
            status_code=422,
            detail="Chinese learning history range cannot exceed 31 days",
        )
    if effective_from < now - CHINESE_HISTORY_RETENTION:
        raise HTTPException(
            status_code=422, detail="Chinese learning history is retained for 180 days"
        )
    return repository.learning_details(
        household_id,
        child_id,
        from_at=effective_from,
        to_at=effective_to,
        limit=limit,
    )


@router.post("/attempts", response_model=ChineseAttempt, status_code=status.HTTP_201_CREATED)
def submit_attempt(
    household_id: UUID,
    child_id: UUID,
    body: ChineseAttemptRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
    profiles: Profiles,
) -> JSONResponse:
    grade = _authorize(household_id, child_id, principal, profiles)
    if principal.role is not AccountRole.CHILD:
        raise HTTPException(status_code=403, detail="bound child principal required")
    try:
        attempt, replayed = repository.submit_attempt(
            household_id, child_id, grade, body, idempotency_key
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail="content not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=409, detail="idempotency key reused with a different payload"
        ) from error
    return JSONResponse(
        status_code=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        content=attempt.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


@router.get("/reviews", response_model=list[ChineseReviewItem])
def list_reviews(
    household_id: UUID,
    child_id: UUID,
    principal: Principal,
    repository: Repository,
    profiles: Profiles,
    due_only: Annotated[bool, Query()] = True,
) -> list[ChineseReviewItem]:
    grade = _authorize(household_id, child_id, principal, profiles)
    if principal.role is not AccountRole.CHILD:
        raise HTTPException(status_code=403, detail="bound child principal required")
    return repository.list_reviews(household_id, child_id, grade, due_only)


@router.get("/skill-report", response_model=ChineseSkillReport)
def get_skill_report(
    household_id: UUID,
    child_id: UUID,
    principal: Principal,
    repository: Repository,
    profiles: Profiles,
) -> ChineseSkillReport:
    _authorize(household_id, child_id, principal, profiles)
    require_parent(principal.role)
    return repository.skill_report(household_id, child_id)


@router.post("/poems/publish", status_code=status.HTTP_201_CREATED)
def publish_poems(
    household_id: UUID,
    child_id: UUID,
    body: PublishChinesePoemsRequest,
    principal: Principal,
    repository: Repository,
    profiles: Profiles,
    curriculum: Curriculum,
) -> dict[str, int]:
    """Publish parent-reviewed private poem extraction into this child's question pool."""

    grade = _authorize(household_id, child_id, principal, profiles)
    require_parent(principal.role)
    material = curriculum.get_material_for_snapshot(household_id, child_id, body.snapshot_id)
    snapshot = next(
        (
            candidate
            for candidate in curriculum.list_snapshots(household_id, child_id, published_only=True)
            if candidate.id == body.snapshot_id
        ),
        None,
    )
    if material is None or snapshot is None or material.id != body.material_id:
        raise HTTPException(status_code=404, detail="resource not found")
    if snapshot.subject is not Subject.CHINESE or snapshot.status != "published":
        raise HTTPException(status_code=409, detail="published Chinese curriculum is required")
    if not material.authorization_statement.strip():
        raise HTTPException(status_code=409, detail="curriculum authorization is required")
    return {"published_questions": repository.publish_poems(household_id, child_id, grade, body)}
