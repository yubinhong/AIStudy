"""Household-scoped ChildProfile and Device routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from study_api.auth import AuthenticatedPrincipal, get_principal, require_household, require_parent
from study_api.domain.capture_repository import CaptureRepository
from study_api.domain.models import (
    ChildProfile,
    CreateChildRequest,
    CreateDeviceRequest,
    Device,
)
from study_api.domain.repository import IdempotencyConflictError, InMemoryProfileRepository
from study_api.media_lifecycle import CaptureObjectCascadeDeletion
from study_api.object_storage import CaptureObjectStorage

router = APIRouter(prefix="/households/{household_id}", tags=["profiles"])
Principal = Annotated[AuthenticatedPrincipal, Depends(get_principal)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


def get_repository(request: Request) -> InMemoryProfileRepository:
    return request.app.state.profile_repository


Repository = Annotated[InMemoryProfileRepository, Depends(get_repository)]


def get_capture_repository(request: Request) -> CaptureRepository:
    return request.app.state.capture_repository


CaptureRepositoryDependency = Annotated[CaptureRepository, Depends(get_capture_repository)]


def get_object_storage(request: Request) -> CaptureObjectStorage:
    return request.app.state.object_storage


ObjectStorageDependency = Annotated[CaptureObjectStorage, Depends(get_object_storage)]


@router.get("/children", response_model=list[ChildProfile])
def list_children(
    household_id: UUID, principal: Principal, repository: Repository
) -> list[ChildProfile]:
    require_household(principal, household_id)
    return repository.list_children(household_id)


@router.post("/children", response_model=ChildProfile, status_code=status.HTTP_201_CREATED)
def create_child(
    household_id: UUID,
    request: CreateChildRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
) -> JSONResponse:
    role = require_household(principal, household_id)
    require_parent(role)
    try:
        child, replayed = repository.create_child(household_id, request, idempotency_key)
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency key reused with a different payload",
        ) from error
    return JSONResponse(
        status_code=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        content=child.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


@router.get("/children/{child_id}", response_model=ChildProfile)
def get_child(
    household_id: UUID, child_id: UUID, principal: Principal, repository: Repository
) -> ChildProfile:
    require_household(principal, household_id)
    child = repository.get_child(household_id, child_id)
    if child is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    return child


@router.delete("/children/{child_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_child(
    household_id: UUID,
    child_id: UUID,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
    capture_repository: CaptureRepositoryDependency,
    object_storage: ObjectStorageDependency,
) -> Response:
    """Delete a synthetic child profile only after all Capture objects are gone."""

    role = require_household(principal, household_id)
    require_parent(role)
    cascade = CaptureObjectCascadeDeletion(capture_repository, object_storage)
    try:
        result = cascade.run_once(household_id, child_id)
    except Exception as error:  # noqa: BLE001 -- do not expose repository failures.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="child deletion is temporarily unavailable",
        ) from error
    if result.failed:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="child deletion is incomplete and can be retried",
        )
    deleted, replayed = repository.delete_child(household_id, child_id, idempotency_key)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    headers = {"Idempotency-Replayed": "true"} if replayed else {}
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers=headers)


@router.get("/devices", response_model=list[Device])
def list_devices(household_id: UUID, principal: Principal, repository: Repository) -> list[Device]:
    role = require_household(principal, household_id)
    require_parent(role)
    return repository.list_devices(household_id)


@router.post("/devices", response_model=Device, status_code=status.HTTP_201_CREATED)
def register_device(
    household_id: UUID,
    request: CreateDeviceRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
) -> JSONResponse:
    role = require_household(principal, household_id)
    require_parent(role)
    try:
        device, replayed = repository.create_device(household_id, request, idempotency_key)
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency key reused with a different payload",
        ) from error
    return JSONResponse(
        status_code=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        content=device.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )
