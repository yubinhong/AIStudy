"""Capture metadata and manual correction routes for synthetic local/CI use."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from study_api.auth import DemoPrincipal, get_demo_principal, require_bound_child, require_household
from study_api.domain.capture_repository import CaptureRepository
from study_api.domain.learning_repository import ChildAssignmentError, ResourceVersionConflictError
from study_api.domain.models import (
    Capture,
    CaptureCorrection,
    CorrectCaptureRequest,
    CreateCaptureRequest,
)
from study_api.domain.repository import IdempotencyConflictError

router = APIRouter(prefix="/households/{household_id}", tags=["captures"])
Principal = Annotated[DemoPrincipal, Depends(get_demo_principal)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


def get_capture_repository(request: Request) -> CaptureRepository:
    return request.app.state.capture_repository


Repository = Annotated[CaptureRepository, Depends(get_capture_repository)]


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")


@router.get("/sessions/{session_id}/captures", response_model=list[Capture])
def list_captures(
    household_id: UUID, session_id: UUID, principal: Principal, repository: Repository
) -> list[Capture]:
    require_household(principal, household_id)
    child_id = require_bound_child(principal)
    try:
        return repository.list_captures(household_id, session_id, child_id)
    except (LookupError, ChildAssignmentError) as error:
        raise _not_found() from error


@router.post(
    "/sessions/{session_id}/captures", response_model=Capture, status_code=status.HTTP_201_CREATED
)
def create_capture(
    household_id: UUID,
    session_id: UUID,
    request: CreateCaptureRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
) -> JSONResponse:
    require_household(principal, household_id)
    child_id = require_bound_child(principal)
    try:
        capture, replayed = repository.create_capture(
            household_id, session_id, child_id, request, idempotency_key
        )
    except (LookupError, ChildAssignmentError) as error:
        raise _not_found() from error
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency key reused with a different payload",
        ) from error
    return JSONResponse(
        status_code=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        content=capture.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


@router.post(
    "/captures/{capture_id}/corrections",
    response_model=CaptureCorrection,
    status_code=status.HTTP_201_CREATED,
)
def correct_capture(
    household_id: UUID,
    capture_id: UUID,
    request: CorrectCaptureRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
) -> JSONResponse:
    require_household(principal, household_id)
    child_id = require_bound_child(principal)
    try:
        correction, replayed = repository.correct_capture(
            household_id, capture_id, child_id, request, idempotency_key
        )
    except (LookupError, ChildAssignmentError) as error:
        raise _not_found() from error
    except ResourceVersionConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="capture version conflict"
        ) from error
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency key reused with a different payload",
        ) from error
    return JSONResponse(
        status_code=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        content=correction.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )
