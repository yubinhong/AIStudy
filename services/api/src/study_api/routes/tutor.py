"""Safe, provider-free Tutor hint route."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from study_api.auth import (
    AuthenticatedPrincipal,
    get_principal,
    require_bound_child,
    require_household,
)
from study_api.domain.capture_repository import CaptureRepository
from study_api.domain.learning_repository import ChildAssignmentError
from study_api.domain.repository import IdempotencyConflictError
from study_api.domain.tutor_turn_repository import TutorTurnRepository
from study_api.domain.verified_question_repository import VerifiedQuestionRepository
from study_api.tutor_policy import (
    StartTutorHintRequest,
    TutorHintRequest,
    TutorHintResponse,
    create_offline_hint,
)

router = APIRouter(prefix="/households/{household_id}", tags=["tutor"])
Principal = Annotated[AuthenticatedPrincipal, Depends(get_principal)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


def get_capture_repository(request: Request) -> CaptureRepository:
    return request.app.state.capture_repository


CaptureRepo = Annotated[CaptureRepository, Depends(get_capture_repository)]


def get_verified_question_repository(request: Request) -> VerifiedQuestionRepository:
    return request.app.state.verified_question_repository


def get_tutor_turn_repository(request: Request) -> TutorTurnRepository:
    return request.app.state.tutor_turn_repository


VerifiedRepo = Annotated[VerifiedQuestionRepository, Depends(get_verified_question_repository)]
TutorTurnRepo = Annotated[TutorTurnRepository, Depends(get_tutor_turn_repository)]


@router.post("/tutor/hints", response_model=TutorHintResponse)
def create_tutor_hint(
    household_id: UUID,
    request: StartTutorHintRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    captures: CaptureRepo,
    verified_questions: VerifiedRepo,
    tutor_turns: TutorTurnRepo,
) -> JSONResponse:
    require_household(principal, household_id)
    child_id = require_bound_child(principal)
    try:
        verified_question = verified_questions.get_by_id(
            household_id, child_id, request.verified_question_id
        )
        capture = captures.get_capture(household_id, verified_question.capture_id, child_id)
    except (LookupError, ChildAssignmentError) as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="resource not found"
        ) from error
    if capture.status.value != "corrected":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="capture must be manually confirmed before tutor hints",
        )
    content = create_offline_hint(
        TutorHintRequest(verified_question=verified_question, level=request.level)
    )
    try:
        turn, replayed = tutor_turns.create(
            household_id,
            child_id,
            verified_question.id,
            content,
            idempotency_key,
        )
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency key reused with a different payload",
        ) from error
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=turn.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )
