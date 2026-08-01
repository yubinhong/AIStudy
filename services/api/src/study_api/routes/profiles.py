"""Household-scoped ChildProfile and Device routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from study_api.auth import (
    AuthenticatedPrincipal,
    get_principal,
    require_bound_child,
    require_household,
    require_parent,
)
from study_api.auth_domain import (
    AccountRepository,
    AccountRole,
    ChildManagementView,
    CreateChildManagementRequest,
    DuplicateUsernameError,
    PasswordPolicyError,
)
from study_api.child_management import ChildManagementRepository
from study_api.domain.capture_repository import CaptureRepository
from study_api.domain.models import (
    ChildProfile,
    CreateChildRequest,
    CreateDeviceRequest,
    Device,
    UpdateChildRequest,
)
from study_api.domain.repository import IdempotencyConflictError, ProfileRepository
from study_api.media_lifecycle import CaptureObjectCascadeDeletion
from study_api.object_storage import CaptureObjectStorage

router = APIRouter(prefix="/households/{household_id}", tags=["profiles"])
Principal = Annotated[AuthenticatedPrincipal, Depends(get_principal)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


def get_repository(request: Request) -> ProfileRepository:
    return request.app.state.profile_repository


Repository = Annotated[ProfileRepository, Depends(get_repository)]


def get_account_repository(request: Request) -> AccountRepository:
    return request.app.state.account_repository


AccountRepositoryDependency = Annotated[AccountRepository, Depends(get_account_repository)]


def get_child_management_repository(request: Request) -> ChildManagementRepository:
    return request.app.state.child_management_repository


ChildManagementRepositoryDependency = Annotated[
    ChildManagementRepository, Depends(get_child_management_repository)
]


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
    role = require_household(principal, household_id)
    if role is AccountRole.CHILD:
        child = repository.get_child(household_id, require_bound_child(principal))
        return [child] if child is not None else []
    return repository.list_children(household_id, owner_account_id=principal.account_id)


def _management_view(request: Request, record) -> ChildManagementView:
    account = (
        request.app.state.auth_service.view(record.account) if record.account is not None else None
    )
    return ChildManagementView(child=record.child, account=account)


@router.get("/children/management", response_model=list[ChildManagementView])
def list_child_management(
    household_id: UUID,
    principal: Principal,
    request: Request,
    management: ChildManagementRepositoryDependency,
) -> list[ChildManagementView]:
    require_parent(require_household(principal, household_id))
    return [
        _management_view(request, item)
        for item in management.list(household_id, principal.account_id)
    ]


@router.post(
    "/children/management",
    response_model=ChildManagementView,
    status_code=status.HTTP_201_CREATED,
)
def create_child_management(
    household_id: UUID,
    body: CreateChildManagementRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    request: Request,
    management: ChildManagementRepositoryDependency,
) -> JSONResponse:
    require_parent(require_household(principal, household_id))
    try:
        record, replayed = management.create(
            household_id, principal.account_id, body, idempotency_key
        )
    except DuplicateUsernameError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="username already exists",
        ) from error
    except PasswordPolicyError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="password is invalid",
        ) from error
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency key reused with a different payload",
        ) from error
    view = _management_view(request, record)
    return JSONResponse(
        status_code=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        content=view.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


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
        child, replayed = repository.create_child(
            household_id, request, idempotency_key, owner_account_id=principal.account_id
        )
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
    role = require_household(principal, household_id)
    if role is AccountRole.CHILD and require_bound_child(principal) != child_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    child = repository.get_child(household_id, child_id)
    if child is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    if role is not AccountRole.CHILD and child.owner_account_id != principal.account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    return child


@router.patch("/children/{child_id}", response_model=ChildProfile)
def update_child(
    household_id: UUID,
    child_id: UUID,
    request: UpdateChildRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
) -> JSONResponse:
    role = require_household(principal, household_id)
    require_parent(role)
    existing = repository.get_child(household_id, child_id)
    if existing is None or existing.owner_account_id != principal.account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    try:
        child, replayed = repository.update_child(household_id, child_id, request, idempotency_key)
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency key reused with a different payload",
        ) from error
    if child is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=child.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


@router.delete("/children/{child_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_child(
    household_id: UUID,
    child_id: UUID,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
    capture_repository: CaptureRepositoryDependency,
    object_storage: ObjectStorageDependency,
    account_repository: AccountRepositoryDependency,
) -> Response:
    """Delete a child profile only after all Capture objects are gone."""

    role = require_household(principal, household_id)
    require_parent(role)
    existing = repository.get_child(household_id, child_id)
    if existing is None or existing.owner_account_id != principal.account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
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
    try:
        account_repository.delete_child_account(household_id, child_id)
    except Exception as error:  # noqa: BLE001 -- do not expose repository failures.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="child account deletion is temporarily unavailable",
        ) from error
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
