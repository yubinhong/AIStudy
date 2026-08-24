"""Independent child-facing picture-writing guidance route.

Unlike math image analysis, this route never creates a QuestionExtraction or
VerifiedQuestion. It reads exactly one already-confirmed sanitized derivative.
"""

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
from study_api.capture_media import read_safe_capture
from study_api.domain.capture_repository import CaptureRepository
from study_api.domain.learning_repository import ChildAssignmentError
from study_api.newapi_provider import NewApiProviderError, NewApiVisionProvider
from study_api.object_storage import CaptureObjectStorage
from study_api.picture_writing import PictureWritingRepository
from study_api.privacy_models import PictureWritingGuideRecord, StartImageAnalysisRequest

router = APIRouter(prefix="/households/{household_id}", tags=["picture-writing"])
Principal = Annotated[AuthenticatedPrincipal, Depends(get_principal)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


def get_capture_repository(request: Request) -> CaptureRepository:
    return request.app.state.capture_repository


def get_object_storage(request: Request) -> CaptureObjectStorage:
    return request.app.state.object_storage


def get_picture_writing_repository(request: Request) -> PictureWritingRepository:
    return request.app.state.picture_writing_repository


CaptureRepo = Annotated[CaptureRepository, Depends(get_capture_repository)]
ObjectStorage = Annotated[CaptureObjectStorage, Depends(get_object_storage)]
Guides = Annotated[PictureWritingRepository, Depends(get_picture_writing_repository)]


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")


@router.post(
    "/captures/{capture_id}/picture-writing-guides",
    response_model=PictureWritingGuideRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_picture_writing_guide(
    household_id: UUID,
    capture_id: UUID,
    body: StartImageAnalysisRequest,
    http_request: Request,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    captures: CaptureRepo,
    storage: ObjectStorage,
    guides: Guides,
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
            detail="capture upload must be confirmed",
        )
    if pending.capture.version != body.expected_capture_version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="capture version conflict")
    if not body.sanitization.safe_to_upload:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="sanitization is not safe to upload",
        )
    if body.sanitization.sanitized_derivative_sha256 != pending.capture.content_sha256:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="sanitization receipt does not match capture",
        )
    config = http_request.app.state.newapi_config
    if not config.enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="picture writing provider is not enabled",
        )
    try:
        safe_capture = read_safe_capture(
            storage,
            pending.object_key,
            pending.capture.media_type,
            pending.capture.byte_size,
            pending.capture.content_sha256,
        )
        guide = NewApiVisionProvider(config).create_picture_writing_guide(
            safe_capture.data,
            pending.capture.media_type,
            sanitization_schema=body.sanitization.schema_version,
        )
        record, replayed = guides.create(
            household_id,
            capture_id,
            child_id,
            idempotency_key,
            guide,
            provider=config.provider_name,
            model=config.vision_model,
        )
    except NewApiProviderError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="picture writing guidance is unavailable",
        ) from error
    except (ValueError, OSError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="confirmed image could not be read",
        ) from error
    return JSONResponse(
        status_code=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        content=record.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


@router.get(
    "/captures/{capture_id}/picture-writing-guides/{guide_id}",
    response_model=PictureWritingGuideRecord,
)
def get_picture_writing_guide(
    household_id: UUID,
    capture_id: UUID,
    guide_id: UUID,
    principal: Principal,
    guides: Guides,
) -> PictureWritingGuideRecord:
    require_household(principal, household_id)
    child_id = require_bound_child(principal)
    try:
        return guides.get(household_id, capture_id, child_id, guide_id)
    except LookupError as error:
        raise _not_found() from error
