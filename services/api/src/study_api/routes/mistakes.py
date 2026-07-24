"""Verified-question mistake records and due review routes."""

from datetime import UTC, datetime
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
from study_api.domain.mistake_repository import (
    CreateMistakeRequest,
    MistakeCloseoutRequest,
    MistakeCloseoutResult,
    MistakeRepository,
    MistakeWithSchedule,
    ReviewMistakeRequest,
)
from study_api.domain.models import AccountRole
from study_api.domain.repository import IdempotencyConflictError

router = APIRouter(prefix="/households/{household_id}", tags=["mistakes"])
Principal = Annotated[AuthenticatedPrincipal, Depends(get_principal)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


def get_repository(request: Request) -> MistakeRepository:
    return request.app.state.mistake_repository


Repository = Annotated[MistakeRepository, Depends(get_repository)]


def _child_scope(principal: AuthenticatedPrincipal, household_id: UUID, child_id: UUID) -> None:
    role = require_household(principal, household_id)
    if role is AccountRole.CHILD and require_bound_child(principal) != child_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")


@router.post(
    "/children/{child_id}/mistake-closeout",
    response_model=MistakeCloseoutResult,
)
def closeout_mistake(
    household_id: UUID,
    child_id: UUID,
    request: MistakeCloseoutRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
) -> JSONResponse:
    """Atomically finish a capture session and persist only an evidence-backed mistake."""

    _child_scope(principal, household_id, child_id)
    try:
        result, replayed = repository.closeout(
            household_id, child_id, request, idempotency_key
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail="resource not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=409,
            detail="idempotency key reused with a different payload",
        ) from error
    return JSONResponse(
        status_code=200,
        content=result.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


@router.post(
    "/children/{child_id}/mistakes",
    response_model=MistakeWithSchedule,
    status_code=status.HTTP_201_CREATED,
)
def create_mistake(
    household_id: UUID,
    child_id: UUID,
    request: CreateMistakeRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
) -> JSONResponse:
    _child_scope(principal, household_id, child_id)
    try:
        result, replayed = repository.create_mistake(
            household_id, child_id, request, idempotency_key
        )
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
        status_code=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        content=result.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


@router.get("/children/{child_id}/mistakes", response_model=list[MistakeWithSchedule])
def list_mistakes(
    household_id: UUID,
    child_id: UUID,
    principal: Principal,
    repository: Repository,
    due_only: Annotated[bool, Query()] = False,
) -> list[MistakeWithSchedule]:
    _child_scope(principal, household_id, child_id)
    return repository.list_mistakes(
        household_id,
        child_id,
        datetime.now(UTC) if due_only else None,
    )


@router.post(
    "/children/{child_id}/mistakes/{mistake_id}/review",
    response_model=MistakeWithSchedule,
)
def review_mistake(
    household_id: UUID,
    child_id: UUID,
    mistake_id: UUID,
    request: ReviewMistakeRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
) -> JSONResponse:
    _child_scope(principal, household_id, child_id)
    try:
        result, replayed = repository.review_mistake(
            household_id, child_id, mistake_id, request, idempotency_key
        )
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="resource not found"
        ) from error
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency key reused with a different payload",
        ) from error
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=result.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )
