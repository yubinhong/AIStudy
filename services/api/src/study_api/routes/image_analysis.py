"""Provider-neutral ImageAnalysis routes.

The route validates the local sanitization receipt and records a blocked job
until a Provider is explicitly approved. It never reads image bytes or calls a
remote service.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from study_api.auth import DemoPrincipal, get_demo_principal, require_bound_child, require_household
from study_api.domain.capture_repository import CaptureRepository
from study_api.domain.learning_repository import ChildAssignmentError
from study_api.domain.question_extraction_repository import QuestionExtractionRepository
from study_api.domain.repository import IdempotencyConflictError
from study_api.image_analysis_jobs import (
    ImageAnalysisJobRepository,
)
from study_api.privacy_models import (
    ImageAnalysisJobReceipt,
    ImageAnalysisJobStatus,
    QuestionExtractionRecord,
    StartImageAnalysisRequest,
)

router = APIRouter(prefix="/households/{household_id}", tags=["image-analysis"])
Principal = Annotated[DemoPrincipal, Depends(get_demo_principal)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


def get_capture_repository(request: Request) -> CaptureRepository:
    return request.app.state.capture_repository


def get_image_analysis_repository(request: Request) -> ImageAnalysisJobRepository:
    return request.app.state.image_analysis_repository


def get_question_extraction_repository(request: Request) -> QuestionExtractionRepository:
    return request.app.state.question_extraction_repository


CaptureRepo = Annotated[CaptureRepository, Depends(get_capture_repository)]
ImageAnalysisRepo = Annotated[ImageAnalysisJobRepository, Depends(get_image_analysis_repository)]
QuestionExtractionRepo = Annotated[
    QuestionExtractionRepository, Depends(get_question_extraction_repository)
]


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")


@router.post(
    "/captures/{capture_id}/image-analysis-jobs",
    response_model=ImageAnalysisJobReceipt,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_image_analysis(
    household_id: UUID,
    capture_id: UUID,
    request: StartImageAnalysisRequest,
    http_request: Request,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    captures: CaptureRepo,
    jobs: ImageAnalysisRepo,
) -> JSONResponse:
    require_household(principal, household_id)
    child_id = require_bound_child(principal)
    try:
        pending = captures.get_capture_upload(household_id, capture_id, child_id)
    except (LookupError, ChildAssignmentError) as error:
        raise _not_found() from error
    if pending.capture.status.value == "upload_pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="capture upload must be confirmed before image analysis",
        )
    if pending.capture.version != request.expected_capture_version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="capture version conflict")

    safe_receipt = request.sanitization.safe_to_upload
    hash_matches = (
        request.sanitization.sanitized_derivative_sha256 == pending.capture.content_sha256
    )
    if not safe_receipt:
        error_code = "sanitization_blocked"
    elif not request.user_confirmed:
        error_code = "sanitization_not_confirmed"
    elif not hash_matches:
        error_code = "sanitization_hash_mismatch"
    elif not http_request.app.state.newapi_config.enabled:
        error_code = "provider_not_enabled"
    else:
        error_code = None
    job_status = (
        ImageAnalysisJobStatus.QUEUED if error_code is None else ImageAnalysisJobStatus.BLOCKED
    )
    try:
        job, replayed = jobs.create(
            household_id,
            capture_id,
            child_id,
            idempotency_key,
            request,
            status=job_status,
            error_code=error_code,
        )
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency key reused with a different payload",
        ) from error
    return JSONResponse(
        status_code=status.HTTP_200_OK if replayed else status.HTTP_202_ACCEPTED,
        content=job.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


@router.get(
    "/captures/{capture_id}/image-analysis-jobs/{job_id}",
    response_model=ImageAnalysisJobReceipt,
)
def get_image_analysis(
    household_id: UUID,
    capture_id: UUID,
    job_id: UUID,
    principal: Principal,
    jobs: ImageAnalysisRepo,
) -> ImageAnalysisJobReceipt:
    require_household(principal, household_id)
    child_id = require_bound_child(principal)
    try:
        return jobs.get(household_id, capture_id, child_id, job_id)
    except LookupError as error:
        raise _not_found() from error


@router.get(
    "/captures/{capture_id}/image-analysis-jobs/{job_id}/extraction",
    response_model=QuestionExtractionRecord,
)
def get_question_extraction(
    household_id: UUID,
    capture_id: UUID,
    job_id: UUID,
    principal: Principal,
    jobs: ImageAnalysisRepo,
    extractions: QuestionExtractionRepo,
) -> QuestionExtractionRecord:
    """Return an unverified extraction for child/parent manual review."""

    require_household(principal, household_id)
    try:
        job = jobs.get_for_household(household_id, capture_id, job_id)
    except LookupError as error:
        raise _not_found() from error
    if job.extraction_id is None or job.status is not ImageAnalysisJobStatus.SUCCEEDED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="extraction is not ready")
    try:
        return extractions.get(household_id, capture_id, job.extraction_id, job.child_id)
    except LookupError as error:
        raise _not_found() from error
