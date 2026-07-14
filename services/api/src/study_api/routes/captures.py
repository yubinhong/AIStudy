"""Capture metadata and manual correction routes for synthetic local/CI use."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response

from study_api.auth import (
    DemoPrincipal,
    get_demo_principal,
    require_bound_child,
    require_household,
    require_parent,
)
from study_api.domain.capture_repository import CaptureRepository, CaptureStateError
from study_api.domain.learning_repository import ChildAssignmentError, ResourceVersionConflictError
from study_api.domain.models import (
    Capture,
    CaptureCorrection,
    CaptureStatus,
    CaptureUpload,
    ConfirmCaptureUploadRequest,
    CorrectCaptureRequest,
    CreateCaptureRequest,
)
from study_api.domain.repository import IdempotencyConflictError
from study_api.media_lifecycle import SingleCaptureObjectDeletion
from study_api.object_storage import CaptureObjectStorage, ObjectStorageError

router = APIRouter(prefix="/households/{household_id}", tags=["captures"])
Principal = Annotated[DemoPrincipal, Depends(get_demo_principal)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


def get_capture_repository(request: Request) -> CaptureRepository:
    return request.app.state.capture_repository


Repository = Annotated[CaptureRepository, Depends(get_capture_repository)]


def get_object_storage(request: Request) -> CaptureObjectStorage:
    return request.app.state.object_storage


ObjectStorage = Annotated[CaptureObjectStorage, Depends(get_object_storage)]


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
    "/sessions/{session_id}/capture-uploads",
    response_model=CaptureUpload,
    status_code=status.HTTP_201_CREATED,
)
def begin_capture_upload(
    household_id: UUID,
    session_id: UUID,
    request: CreateCaptureRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
    object_storage: ObjectStorage,
) -> JSONResponse:
    """Issue a short-lived private upload URL without a separate object-key field."""

    require_household(principal, household_id)
    child_id = require_bound_child(principal)
    try:
        pending, replayed = repository.begin_capture_upload(
            household_id, session_id, child_id, request, idempotency_key
        )
        object_storage.ensure_bucket()
        signed_upload = object_storage.create_put_url(
            pending.object_key, pending.capture.media_type, pending.capture.byte_size
        )
    except (LookupError, ChildAssignmentError) as error:
        raise _not_found() from error
    except CaptureStateError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="capture upload is no longer pending"
        ) from error
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency key reused with a different payload",
        ) from error
    except ObjectStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="capture upload is temporarily unavailable",
        ) from error
    body = CaptureUpload(
        capture=pending.capture,
        upload_url=signed_upload.url,
        upload_expires_at=signed_upload.expires_at,
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        content=body.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


@router.post(
    "/captures/{capture_id}/upload-confirmations",
    response_model=Capture,
    status_code=status.HTTP_201_CREATED,
)
def confirm_capture_upload(
    household_id: UUID,
    capture_id: UUID,
    request: ConfirmCaptureUploadRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
    object_storage: ObjectStorage,
) -> JSONResponse:
    """Advance only a server-validated private object to manual correction."""

    require_household(principal, household_id)
    child_id = require_bound_child(principal)
    try:
        pending = repository.get_capture_upload(household_id, capture_id, child_id)
        if pending.capture.status is CaptureStatus.UPLOAD_PENDING:
            object_storage.validate_uploaded_object(
                pending.object_key, pending.capture.media_type, pending.capture.byte_size
            )
        capture, replayed = repository.confirm_capture_upload(
            household_id, capture_id, child_id, request, idempotency_key
        )
    except (LookupError, ChildAssignmentError) as error:
        raise _not_found() from error
    except ResourceVersionConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="capture version conflict"
        ) from error
    except CaptureStateError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="capture upload is not pending"
        ) from error
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency key reused with a different payload",
        ) from error
    except ObjectStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="uploaded capture object could not be verified",
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
    except CaptureStateError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="capture is not ready for correction"
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


@router.post("/captures/{capture_id}/save", status_code=status.HTTP_204_NO_CONTENT)
def save_capture(
    household_id: UUID,
    capture_id: UUID,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
) -> Response:
    """Let a parent opt out of the bounded automatic image retention window."""

    require_parent(require_household(principal, household_id))
    try:
        replayed = repository.save_capture(household_id, capture_id, idempotency_key)
    except LookupError as error:
        raise _not_found() from error
    except CaptureStateError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="capture cannot be saved in its current state",
        ) from error
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency key reused with a different payload",
        ) from error
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


@router.delete("/captures/{capture_id}/media", status_code=status.HTTP_204_NO_CONTENT)
def delete_capture_media(
    household_id: UUID,
    capture_id: UUID,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
    object_storage: ObjectStorage,
) -> Response:
    """Immediately delete one private Capture object under parent authorization."""

    require_parent(require_household(principal, household_id))
    deletion = SingleCaptureObjectDeletion(repository, object_storage)
    try:
        _, replayed = deletion.run_once(household_id, capture_id, idempotency_key)
    except LookupError as error:
        raise _not_found() from error
    except CaptureStateError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="capture cannot be deleted in its current state",
        ) from error
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency key reused with a different payload",
        ) from error
    except ObjectStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="capture deletion is temporarily unavailable",
        ) from error
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )
