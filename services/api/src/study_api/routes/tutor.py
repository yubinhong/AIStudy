"""Tutor hints and solutions bounded by approved curriculum knowledge."""

from difflib import SequenceMatcher
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
from study_api.curriculum_analysis_jobs import CurriculumKnowledgeRepository
from study_api.domain.capture_repository import CaptureRepository
from study_api.domain.curriculum_knowledge import CurriculumKnowledgePoint
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


def get_curriculum_knowledge_repository(request: Request) -> CurriculumKnowledgeRepository:
    return request.app.state.curriculum_knowledge_repository


KnowledgeRepo = Annotated[
    CurriculumKnowledgeRepository, Depends(get_curriculum_knowledge_repository)
]


def _compact(value: str) -> str:
    return "".join(value.lower().split())


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left in right or right in left:
        return 1.0
    return SequenceMatcher(None, left, right).ratio()


def _scope_score(question_text: str, point: CurriculumKnowledgePoint) -> float:
    """Prefer an exact approved exercise; otherwise require meaningful overlap."""

    question = _compact(question_text)
    exercise_score = max(
        (_similarity(question, _compact(exercise.question_text)) for exercise in point.exercises),
        default=0.0,
    )
    scope_text = _compact(
        " ".join(
            (
                point.chapter_title,
                point.section_title,
                point.title,
                point.summary,
                *point.learning_objectives,
                *point.prerequisites,
            )
        )
    )
    lexical_score = _similarity(question, scope_text)
    if "/" in question and "分数" in scope_text:
        lexical_score = max(lexical_score, 0.36)
    return max(exercise_score, lexical_score * 0.75)


def _select_curriculum_scope(
    knowledge: CurriculumKnowledgeRepository,
    household_id: UUID,
    child_id: UUID,
    question_text: str,
) -> CurriculumKnowledgePoint | None:
    points = knowledge.list_approved_points(household_id, child_id)
    scored = sorted(
        ((_scope_score(question_text, point), point) for point in points),
        key=lambda value: (value[0], value[1].confidence),
        reverse=True,
    )
    if not scored or scored[0][0] < 0.55:
        return None
    return scored[0][1]


def _provider_scope(point: CurriculumKnowledgePoint) -> dict[str, object]:
    return {
        "knowledge_key": point.knowledge_key,
        "title": point.title,
        "chapter_title": point.chapter_title,
        "section_title": point.section_title,
        "summary": point.summary,
        "learning_objectives": list(point.learning_objectives),
        "allowed_prerequisites": list(point.prerequisites),
        "source_pages": list(point.page_numbers),
    }


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
    knowledge: KnowledgeRepo,
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
        grounded_point = _select_curriculum_scope(
            knowledge, household_id, child_id, verified_question.question_text
        )
    except Exception:  # noqa: BLE001 - retain the non-provider hint fallback on read failure
        grounded_point = None
    provider_scope = _provider_scope(grounded_point) if grounded_point is not None else None
    if grounded_point is not None:
        content = content.model_copy(
            update={
                "curriculum_sources": tuple(
                    CurriculumSource(
                        snapshot_id=grounded_point.snapshot_id,
                        page_number=page_number,
                        title=grounded_point.title,
                        confidence=grounded_point.confidence,
                    )
                    for page_number in grounded_point.page_numbers[:5]
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
                curriculum_excerpts=(),
                curriculum_scope=provider_scope,
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
                curriculum_scope=provider_scope,
            )
        except NewApiProviderError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="detailed solution is temporarily unavailable",
            ) from error
        content = content.model_copy(
            update={
                "policy_version": (
                    "verified-solution-policy.v1"
                    if provider_scope is not None
                    else "general-solution-policy.v1"
                ),
                "provider": "newapi",
                "model": provider_config.vision_model,
                "prompt": (
                    "下面给出完整解答，请逐步对照题目和自己的作答。"
                    if provider_scope is not None
                    else "下面给出完整解答。当前没有匹配到教材知识点，"
                    "先用适龄的基础方法讲清楚这道题。"
                ),
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
