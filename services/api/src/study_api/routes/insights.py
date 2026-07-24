"""Household-scoped parent learning reports and detailed traces."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from study_api.auth import (
    AuthenticatedPrincipal,
    get_principal,
    require_bound_child,
    require_household,
)
from study_api.domain.insights_repository import (
    ChildDataExport,
    InsightsRepository,
    LearningDetail,
    WeeklyReport,
)
from study_api.domain.models import AccountRole
from study_api.domain.repository import IdempotencyConflictError, ProfileRepository

router = APIRouter(prefix="/households/{household_id}", tags=["insights"])
Principal = Annotated[AuthenticatedPrincipal, Depends(get_principal)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


def get_insights_repository(request: Request) -> InsightsRepository:
    return request.app.state.insights_repository


def get_profile_repository(request: Request) -> ProfileRepository:
    return request.app.state.profile_repository


InsightsRepo = Annotated[InsightsRepository, Depends(get_insights_repository)]
ProfileRepo = Annotated[ProfileRepository, Depends(get_profile_repository)]


@router.get("/reports/weekly", response_model=WeeklyReport)
def get_weekly_report(
    household_id: UUID,
    child_id: Annotated[UUID, Query()],
    week_start: Annotated[date, Query()],
    principal: Principal,
    profiles: ProfileRepo,
    insights: InsightsRepo,
) -> WeeklyReport:
    role = require_household(principal, household_id)
    if role is AccountRole.CHILD and require_bound_child(principal) != child_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    if profiles.get_child(household_id, child_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    return insights.weekly_report(household_id, child_id, week_start)


@router.get(
    "/children/{child_id}/learning-details",
    response_model=list[LearningDetail],
)
def get_learning_details(
    household_id: UUID,
    child_id: UUID,
    principal: Principal,
    profiles: ProfileRepo,
    insights: InsightsRepo,
    limit: int = 20,
) -> tuple[LearningDetail, ...]:
    role = require_household(principal, household_id)
    if role is not AccountRole.PARENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="parent required")
    if profiles.get_child(household_id, child_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
    return insights.learning_details(household_id, child_id, limit)


@router.post("/children/{child_id}/exports", response_model=ChildDataExport)
def export_child_data(
    household_id: UUID,
    child_id: UUID,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    profiles: ProfileRepo,
    insights: InsightsRepo,
) -> JSONResponse:
    role = require_household(principal, household_id)
    if role is not AccountRole.PARENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="parent required")
    if profiles.get_child(household_id, child_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    try:
        export, replayed = insights.export_child(household_id, child_id, idempotency_key)
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency key reused with a different payload",
        ) from error
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="resource not found"
        ) from error
    return JSONResponse(
        content=export.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )
