"""Generate source-backed task plans and require parent approval."""

from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from study_api.auth import AuthenticatedPrincipal, get_principal, require_household, require_parent
from study_api.curriculum_analysis_jobs import CurriculumKnowledgeRepository
from study_api.domain.curriculum_repository import CurriculumRepository
from study_api.domain.mistake_repository import MistakeRepository
from study_api.domain.models import AccountRole, CreateTaskRequest, Subject
from study_api.domain.recommendation_repository import (
    CreateRecommendationRequest,
    DecideRecommendationRequest,
    RecommendationDecision,
    TaskRecommendation,
    TaskRecommendationRepository,
)
from study_api.domain.repository import IdempotencyConflictError
from study_api.domain.sql_learning_repository import LearningRepository
from study_api.newapi_provider import NewApiProviderError, NewApiVisionProvider
from study_api.recommendation_engine import (
    build_recommendation_sources,
    resolve_provider_plan,
)

router = APIRouter(prefix="/households/{household_id}", tags=["recommendations"])
Principal = Annotated[AuthenticatedPrincipal, Depends(get_principal)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


def get_repository(request: Request) -> TaskRecommendationRepository:
    return request.app.state.recommendation_repository


def get_mistakes(request: Request) -> MistakeRepository:
    return request.app.state.mistake_repository


def get_curriculum(request: Request) -> CurriculumRepository:
    return request.app.state.curriculum_repository


def get_learning(request: Request) -> LearningRepository:
    return request.app.state.learning_repository


def get_knowledge(request: Request) -> CurriculumKnowledgeRepository:
    return request.app.state.curriculum_knowledge_repository


Repository = Annotated[TaskRecommendationRepository, Depends(get_repository)]
Mistakes = Annotated[MistakeRepository, Depends(get_mistakes)]
Curriculum = Annotated[CurriculumRepository, Depends(get_curriculum)]
Learning = Annotated[LearningRepository, Depends(get_learning)]
Knowledge = Annotated[CurriculumKnowledgeRepository, Depends(get_knowledge)]


def _require_child(
    principal: AuthenticatedPrincipal, request: Request, household_id: UUID, child_id: UUID
) -> None:
    child = request.app.state.profile_repository.get_child(household_id, child_id)
    if (
        child is None
        or (principal.role is AccountRole.CHILD and principal.child_id != child_id)
        or (
            principal.role is not AccountRole.CHILD
            and child.owner_account_id != principal.account_id
        )
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")


@router.post(
    "/children/{child_id}/task-recommendations",
    response_model=list[TaskRecommendation],
)
def generate_recommendations(
    household_id: UUID,
    child_id: UUID,
    payload: CreateRecommendationRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
    mistakes: Mistakes,
    curriculum: Curriculum,
    knowledge: Knowledge,
    app_request: Request,
) -> list[TaskRecommendation]:
    require_parent(require_household(principal, household_id))
    _require_child(principal, app_request, household_id, child_id)
    if payload.child_id != child_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="child scope mismatch")
    now = datetime.now(UTC)
    all_mistakes = mistakes.list_mistakes(household_id, child_id)
    snapshots = curriculum.list_snapshots(household_id, child_id, published_only=True)
    knowledge_points = [
        point
        for snapshot in snapshots
        for point in knowledge.list_approved_points(household_id, child_id, snapshot.id)
    ]
    if snapshots and not knowledge_points:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="published curriculum has no approved AI knowledge map",
        )
    sources = build_recommendation_sources(all_mistakes, knowledge_points, now=now)
    if not sources:
        return []
    provider_config = app_request.app.state.newapi_config
    if not provider_config.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="intelligent recommendation provider is not configured",
        )
    try:
        plan = NewApiVisionProvider(provider_config).create_recommendation_plan(sources=sources)
        drafts = resolve_provider_plan(
            plan,
            sources,
            today=date.today(),
            provider="newapi",
            model=provider_config.vision_model,
        )
    except (NewApiProviderError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="intelligent recommendation planning failed safely",
        ) from error

    results: list[TaskRecommendation] = []
    for index, draft in enumerate(drafts):
        try:
            recommendation, _ = repository.generate(
                household_id,
                child_id,
                draft,
                f"{idempotency_key}-{index}",
            )
        except IdempotencyConflictError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="idempotency key reused with a different payload",
            ) from error
        results.append(recommendation)
    return results


@router.get(
    "/children/{child_id}/task-recommendations",
    response_model=list[TaskRecommendation],
)
def list_recommendations(
    household_id: UUID,
    child_id: UUID,
    principal: Principal,
    repository: Repository,
    app_request: Request,
    pending_only: Annotated[bool, Query()] = False,
) -> list[TaskRecommendation]:
    require_household(principal, household_id)
    _require_child(principal, app_request, household_id, child_id)
    return repository.list(household_id, child_id, pending_only)


@router.post(
    "/children/{child_id}/task-recommendations/{recommendation_id}/decision",
    response_model=TaskRecommendation,
)
def decide_recommendation(
    household_id: UUID,
    child_id: UUID,
    recommendation_id: UUID,
    request: DecideRecommendationRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
    learning: Learning,
    app_request: Request,
) -> JSONResponse:
    require_parent(require_household(principal, household_id))
    _require_child(principal, app_request, household_id, child_id)
    try:
        recommendation, replayed = repository.decide(
            household_id, child_id, recommendation_id, request, idempotency_key
        )
        if request.decision is RecommendationDecision.APPROVE and recommendation.task_id is None:
            task, _ = learning.create_task(
                household_id,
                CreateTaskRequest(
                    child_id=child_id,
                    title=recommendation.title,
                    subject=Subject.MATH,
                    scheduled_for=recommendation.scheduled_for,
                    source_type=recommendation.source_type,
                    reason=recommendation.reason,
                    knowledge_point=recommendation.knowledge_point,
                    knowledge_point_id=recommendation.knowledge_point_id,
                    exercises=recommendation.exercises,
                    estimated_minutes=recommendation.estimated_minutes,
                ),
                f"recommendation-task-{recommendation.id}",
            )
            recommendation = repository.attach_task(household_id, recommendation.id, task.id)
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="resource not found"
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency key reused with a different payload",
        ) from error
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=recommendation.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )
