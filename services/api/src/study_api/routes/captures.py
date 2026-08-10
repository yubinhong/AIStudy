"""Capture metadata and manual correction routes for synthetic local/CI use."""

import asyncio
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response

from study_api.auth import (
    AuthenticatedPrincipal,
    get_principal,
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
    ConfirmOcrCandidateRequest,
    CorrectCaptureRequest,
    CreateCaptureRequest,
    EnqueueOcrJobRequest,
    OcrJobReceipt,
    OcrMode,
    OcrResultWithCandidates,
)
from study_api.domain.ocr_result_repository import OcrResultRepository
from study_api.domain.repository import IdempotencyConflictError
from study_api.media_lifecycle import SingleCaptureObjectDeletion
from study_api.object_storage import CaptureObjectStorage, ObjectStorageError
from study_api.ocr_jobs import OcrJobIdempotencyConflictError, OcrJobQueue

router = APIRouter(prefix="/households/{household_id}", tags=["captures"])
Principal = Annotated[AuthenticatedPrincipal, Depends(get_principal)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]
CaptureMediaType = Annotated[
    Literal["image/jpeg", "image/png"], Header(alias="X-Capture-Media-Type")
]
CaptureByteSize = Annotated[int, Header(alias="X-Capture-Byte-Size", ge=1, le=8_000_000)]
CaptureSha256 = Annotated[
    str,
    Header(
        alias="X-Capture-Content-SHA256",
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    ),
]


def get_capture_repository(request: Request) -> CaptureRepository:
    return request.app.state.capture_repository


Repository = Annotated[CaptureRepository, Depends(get_capture_repository)]


def get_object_storage(request: Request) -> CaptureObjectStorage:
    return request.app.state.object_storage


ObjectStorage = Annotated[CaptureObjectStorage, Depends(get_object_storage)]


def get_ocr_job_queue(request: Request) -> OcrJobQueue:
    return request.app.state.ocr_job_queue


OcrQueue = Annotated[OcrJobQueue, Depends(get_ocr_job_queue)]


def get_ocr_result_repository(request: Request) -> OcrResultRepository:
    return request.app.state.ocr_result_repository


OcrResults = Annotated[OcrResultRepository, Depends(get_ocr_result_repository)]


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
    "/sessions/{session_id}/captures/upload",
    response_model=Capture,
    status_code=status.HTTP_201_CREATED,
)
async def upload_capture_stream(
    household_id: UUID,
    session_id: UUID,
    request: Request,
    media_type: CaptureMediaType,
    byte_size: CaptureByteSize,
    content_sha256: CaptureSha256,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
    object_storage: ObjectStorage,
) -> JSONResponse:
    """Receive a bounded Capture body through the authenticated API boundary."""

    # Authorization deliberately happens before request.stream() is consumed.
    require_household(principal, household_id)
    child_id = require_bound_child(principal)
    declared_content_length = request.headers.get("content-length")
    if declared_content_length is not None:
        try:
            if int(declared_content_length) != byte_size:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="capture content length does not match declaration",
                )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="capture content length is invalid",
            ) from error
    metadata = CreateCaptureRequest(
        media_type=media_type,
        byte_size=byte_size,
        content_sha256=content_sha256,
    )
    try:
        pending, replayed = repository.begin_capture_upload(
            household_id, session_id, child_id, metadata, idempotency_key
        )
        if pending.capture.status is CaptureStatus.UPLOAD_PENDING:
            semaphore: asyncio.Semaphore = request.app.state.capture_upload_semaphore
            if semaphore.locked():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="capture upload capacity is temporarily unavailable",
                )
            await semaphore.acquire()
            try:
                await asyncio.wait_for(
                    object_storage.stream_capture_upload(
                        pending.object_key,
                        pending.capture.media_type,
                        pending.capture.byte_size,
                        pending.capture.content_sha256,
                        request.stream(),
                    ),
                    timeout=request.app.state.capture_upload_timeout_seconds,
                )
            finally:
                semaphore.release()
            capture, confirmed_replayed = repository.confirm_capture_upload(
                household_id,
                pending.capture.id,
                child_id,
                ConfirmCaptureUploadRequest(expected_capture_version=pending.capture.version),
                f"stream-finalize-{idempotency_key}",
            )
            replayed = replayed or confirmed_replayed
        else:
            capture = pending.capture
    except (LookupError, ChildAssignmentError) as error:
        raise _not_found() from error
    except CaptureStateError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="capture upload is not pending"
        ) from error
    except ResourceVersionConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="capture version conflict"
        ) from error
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency key reused with a different payload",
        ) from error
    except ObjectStorageError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
                if error.retryable
                else status.HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail=(
                "capture upload is temporarily unavailable"
                if error.retryable
                else "capture image failed bounded validation"
            ),
        ) from error
    except TimeoutError as error:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="capture upload timed out; retry with the same idempotency key",
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
    include_in_schema=False,
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
    include_in_schema=False,
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
                pending.object_key,
                pending.capture.media_type,
                pending.capture.byte_size,
                pending.capture.content_sha256,
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
    "/captures/{capture_id}/ocr-jobs",
    response_model=OcrJobReceipt,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_ocr_job(
    household_id: UUID,
    capture_id: UUID,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
    queue: OcrQueue,
    request: EnqueueOcrJobRequest | None = None,
) -> JSONResponse:
    """Enqueue local OCR after the Capture has passed server-side upload checks."""

    require_household(principal, household_id)
    child_id = require_bound_child(principal)
    try:
        pending = repository.get_capture_upload(household_id, capture_id, child_id)
        if pending.capture.status is CaptureStatus.UPLOAD_PENDING:
            raise CaptureStateError
        job, replayed = queue.enqueue(
            household_id,
            capture_id,
            child_id,
            idempotency_key,
            mode=request.mode if request is not None else OcrMode.TEXT,
        )
    except (LookupError, ChildAssignmentError) as error:
        raise _not_found() from error
    except CaptureStateError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="capture upload is not ready for OCR",
        ) from error
    except OcrJobIdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency key reused with a different OCR mode",
        ) from error
    return JSONResponse(
        status_code=status.HTTP_200_OK if replayed else status.HTTP_202_ACCEPTED,
        content=job.receipt().model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


@router.get(
    "/captures/{capture_id}/ocr-jobs/{job_id}",
    response_model=OcrJobReceipt,
)
def get_ocr_job(
    household_id: UUID,
    capture_id: UUID,
    job_id: UUID,
    principal: Principal,
    repository: Repository,
    queue: OcrQueue,
) -> OcrJobReceipt:
    """Return bounded OCR job status for the bound child without error details."""

    require_household(principal, household_id)
    child_id = require_bound_child(principal)
    try:
        pending = repository.get_capture_upload(household_id, capture_id, child_id)
        job = queue.get(job_id)
    except (LookupError, ChildAssignmentError) as error:
        raise _not_found() from error
    if (
        job.household_id != household_id
        or job.capture_id != pending.capture.id
        or job.child_id != child_id
    ):
        raise _not_found()
    return job.receipt()


@router.get(
    "/captures/{capture_id}/ocr-results/{result_id}",
    response_model=OcrResultWithCandidates,
)
def get_ocr_result(
    household_id: UUID,
    capture_id: UUID,
    result_id: UUID,
    principal: Principal,
    results: OcrResults,
) -> OcrResultWithCandidates:
    """Return unverified OCR candidates for the bound child to confirm."""

    require_household(principal, household_id)
    child_id = require_bound_child(principal)
    try:
        result, candidates = results.get_result(household_id, result_id, child_id)
    except (LookupError, ChildAssignmentError) as error:
        raise _not_found() from error
    if result.capture_id != capture_id:
        raise _not_found()
    return OcrResultWithCandidates(result=result, candidates=candidates)


@router.post(
    "/captures/{capture_id}/ocr-results/{result_id}/confirmations",
    response_model=CaptureCorrection,
    status_code=status.HTTP_201_CREATED,
)
def confirm_ocr_candidate(
    household_id: UUID,
    capture_id: UUID,
    result_id: UUID,
    request: ConfirmOcrCandidateRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
    results: OcrResults,
) -> JSONResponse:
    """Append a selected OCR candidate as a manually confirmed Capture correction."""

    require_household(principal, household_id)
    child_id = require_bound_child(principal)
    try:
        result, candidates = results.get_result(household_id, result_id, child_id)
        if result.capture_id != capture_id:
            raise LookupError
        candidate = next(
            (candidate for candidate in candidates if candidate.id == request.candidate_id),
            None,
        )
        if candidate is None or candidate.result_id != result_id:
            raise LookupError
        correction_request = CorrectCaptureRequest(
            expected_capture_version=request.expected_capture_version,
            corrected_text=candidate.text,
        )
        correction, replayed = repository.correct_capture(
            household_id,
            capture_id,
            child_id,
            correction_request,
            idempotency_key,
            operation_prefix=f"confirm_ocr_candidate:{result_id}",
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
