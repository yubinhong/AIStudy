"""Safe, provider-free Tutor hint route."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from study_api.auth import (
    AuthenticatedPrincipal,
    get_principal,
    require_bound_child,
    require_household,
)
from study_api.domain.capture_repository import CaptureRepository
from study_api.domain.learning_repository import ChildAssignmentError
from study_api.tutor_policy import StartTutorHintRequest, TutorHintResponse, create_offline_hint

router = APIRouter(prefix="/households/{household_id}", tags=["tutor"])
Principal = Annotated[AuthenticatedPrincipal, Depends(get_principal)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


def get_capture_repository(request: Request) -> CaptureRepository:
    return request.app.state.capture_repository


CaptureRepo = Annotated[CaptureRepository, Depends(get_capture_repository)]


@router.post("/tutor/hints", response_model=TutorHintResponse)
def create_tutor_hint(
    household_id: UUID,
    request: StartTutorHintRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    captures: CaptureRepo,
) -> TutorHintResponse:
    del idempotency_key  # Stateless deterministic fallback; no side effect to replay.
    require_household(principal, household_id)
    child_id = require_bound_child(principal)
    if request.child_id != child_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    try:
        capture = captures.get_capture(household_id, request.verified_question.capture_id, child_id)
    except (LookupError, ChildAssignmentError) as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="resource not found"
        ) from error
    if capture.status.value != "corrected":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="capture must be manually confirmed before tutor hints",
        )
    return create_offline_hint(request)
