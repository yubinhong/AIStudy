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
from study_api.domain.curriculum_repository import CurriculumRepository
from study_api.domain.learning_repository import ChildAssignmentError
from study_api.domain.models import AnswerState, CaptureStatus
from study_api.domain.repository import IdempotencyConflictError
from study_api.domain.tutor_turn_repository import TutorTurnRepository
from study_api.domain.verified_question_repository import VerifiedQuestionRepository
from study_api.newapi_provider import NewApiProviderError, NewApiVisionProvider
from study_api.tutor_policy import (
    CurriculumSource,
    StartTutorHintRequest,
    TutorHintRequest,
    TutorHintResponse,
    create_offline_hint,
    validate_generated_hint,
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


def get_curriculum_repository(request: Request) -> CurriculumRepository:
    return request.app.state.curriculum_repository


CurriculumRepo = Annotated[CurriculumRepository, Depends(get_curriculum_repository)]


@router.post("/tutor/hints", response_model=TutorHintResponse)
def create_tutor_hint(
    household_id: UUID,
    request: StartTutorHintRequest,
    app_request: Request,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    captures: CaptureRepo,
    verified_questions: VerifiedRepo,
    tutor_turns: TutorTurnRepo,
    curriculum: CurriculumRepo,
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
    # A VerifiedQuestion can only be created after explicit human review. The
    # visual extraction flow intentionally leaves the Capture itself in
    # ``needs_correction`` while the legacy OCR correction flow advances it to
    # ``corrected``. Both states therefore represent a manually confirmed
    # Tutor-safe question once the server-owned VerifiedQuestion exists.
    if capture.status not in {CaptureStatus.NEEDS_CORRECTION, CaptureStatus.CORRECTED}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="capture must be manually confirmed before tutor hints",
        )
    answer_state = verified_question.answer_state
    evidence_confirmed = verified_question.evidence_confirmed
    mode = request.mode
    if mode == "mistake_explanation":
        if not evidence_confirmed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="mistake explanation requires manually confirmed answer evidence",
            )
        if answer_state in {AnswerState.UNCLEAR, AnswerState.ANSWER_AREA_MISSING}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="answer state must be confirmed before mistake explanation",
            )
    previous = None
    if request.level > 1:
        previous = tutor_turns.latest_before_level(
            household_id, child_id, verified_question.id, request.level
        )
        if request.level == 2 and previous is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="level two requires a persisted level one hint",
            )
    content = create_offline_hint(
        TutorHintRequest(
            verified_question=verified_question,
            level=request.level,
            mode=mode,
            answer_state=answer_state,
        )
    )
    try:
        chunks = curriculum.search_chunks(
            household_id, child_id, verified_question.question_text, limit=3
        )
    except Exception:  # noqa: BLE001 - curriculum grounding is optional and must degrade safely
        chunks = []
    grounded_chunks = tuple(chunk for chunk in chunks if chunk.confidence >= 0.6)
    if grounded_chunks:
        content = content.model_copy(
            update={
                "curriculum_sources": tuple(
                    CurriculumSource(
                        snapshot_id=chunk.snapshot_id,
                        page_number=chunk.page_number,
                        title=chunk.title,
                        confidence=chunk.confidence,
                    )
                    for chunk in grounded_chunks
                )
            }
        )
    if previous is not None:
        content = content.model_copy(update={"builds_on_turn_id": previous.id})
    provider_config = app_request.app.state.newapi_config
    if request.level in {1, 2} and provider_config.enabled:
        provider = NewApiVisionProvider(provider_config)
        previous_payload = (
            {
                "prompt": previous.prompt,
                "next_step": previous.next_step,
                "child_action": previous.child_action,
                "revealed_elements": list(previous.revealed_elements),
            }
            if previous is not None
            else None
        )
        try:
            generated = provider.create_tutor_hint(
                question_text=verified_question.question_text,
                level=request.level,
                answer_state=answer_state.value,
                answer_text=verified_question.answer_text,
                answer_steps=verified_question.answer_steps,
                previous_hint=previous_payload,
                curriculum_excerpts=tuple(
                    {
                        "page_number": chunk.page_number,
                        "title": chunk.title,
                        "text": chunk.text[:1200],
                    }
                    for chunk in grounded_chunks
                ),
            )
            validate_generated_hint(
                generated,
                level=request.level,
                previous=previous,
                question_text=verified_question.question_text,
            )
        except (NewApiProviderError, ValueError):
            # Unsafe, repetitive or malformed cloud output degrades to the
            # question-specific deterministic hint above.
            pass
        else:
            content = content.model_copy(
                update={
                    "policy_version": "cloud-tutor-policy.v1",
                    "provider": "newapi",
                    "model": provider_config.vision_model,
                    "prompt": generated.prompt,
                    "next_step": generated.next_step,
                    "child_action": generated.child_action,
                    "revealed_elements": generated.revealed_elements,
                    "hint_goal": (
                        "understand_the_question" if request.level == 1 else "choose_a_method"
                    ),
                    "answer_exposure": "none",
                    "builds_on_turn_id": previous.id if previous is not None else None,
                }
            )
    if (
        request.level == 3
        and evidence_confirmed
        and answer_state
        in {
            AnswerState.WORKED,
            AnswerState.BLANK,
        }
    ):
        if not provider_config.enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="detailed solution provider is not configured",
            )
        provider = NewApiVisionProvider(provider_config)
        try:
            solution = provider.create_detailed_solution(
                question_text=verified_question.question_text,
                answer_state=answer_state.value,
                answer_text=verified_question.answer_text,
                answer_steps=verified_question.answer_steps,
            )
        except NewApiProviderError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="detailed solution is temporarily unavailable",
            ) from error
        content = content.model_copy(
            update={
                "policy_version": "verified-solution-policy.v1",
                "provider": "newapi",
                "model": provider_config.vision_model,
                "prompt": "下面给出完整解答，请逐步对照题目和自己的作答。",
                "next_step": "看完后用自己的话复述关键一步，并用验算再次确认。",
                "requires_child_response": False,
                "direct_answer": solution.final_answer,
                "solution_steps": solution.steps,
                "verification": solution.verification,
            }
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
