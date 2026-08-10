"""Self-hosted account, password and revocable-session endpoints."""

import os
import secrets
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from study_api.auth import (
    AuthenticatedPrincipal,
    get_principal,
    require_household,
    require_parent,
    require_super_admin,
)
from study_api.auth_domain import (
    AccountView,
    AuthError,
    ChangePasswordRequest,
    CreateChildAccountRequest,
    CreateHouseholdRequest,
    CreateParentAccountRequest,
    DeleteParentAccountRequest,
    DuplicateUsernameError,
    FamilyParentView,
    LoginRequest,
    LoginResponse,
    PasswordPolicyError,
    ResetPasswordRequest,
    SetAccountStatusRequest,
)
from study_api.domain.models import AccountRole
from study_api.domain.repository import IdempotencyConflictError

router = APIRouter(prefix="/auth", tags=["authentication"])
Principal = Annotated[AuthenticatedPrincipal, Depends(get_principal)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


def _cookie_secure() -> bool:
    return os.environ.get("STUDY_COOKIE_SECURE", "false").lower() == "true"


def _set_session_cookie(response: Response, token: str | None, expires_at) -> None:
    if token is None:
        return
    response.set_cookie(
        "study_session",
        token,
        max_age=max(1, int((expires_at - datetime.now(UTC)).total_seconds())),
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )


def _set_csrf_cookie(response: Response) -> None:
    response.set_cookie(
        "study_csrf",
        secrets.token_urlsafe(32),
        max_age=60 * 60 * 24 * 30,
        httponly=False,
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )


def _token(authorization: str | None, session_cookie: str | None) -> str | None:
    if session_cookie:
        return session_cookie
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and value:
            return value
    return None


def _require_parent_reauth(
    principal: AuthenticatedPrincipal, request: Request, password: str
) -> None:
    if principal.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="reauthentication required"
        )
    try:
        request.app.state.auth_service.verify_current_password(principal.account_id, password)
    except (AuthError, LookupError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="reauthentication required"
        ) from error


def _require_owned_child(
    principal: AuthenticatedPrincipal, request: Request, household_id: UUID, child_id: UUID
) -> None:
    child = request.app.state.profile_repository.get_child(household_id, child_id)
    if child is None or child.owner_account_id != principal.account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, http_request: Request) -> JSONResponse:
    try:
        result = http_request.app.state.auth_service.login(
            request, remote_host=http_request.client.host if http_request.client else None
        )
    except (AuthError, PasswordPolicyError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials"
        ) from error
    response = JSONResponse(
        status_code=status.HTTP_200_OK,
        content=result.model_copy(update={"access_token": None}).model_dump(mode="json")
        if request.client == "web"
        else result.model_dump(mode="json"),
    )
    if request.client == "web":
        _set_session_cookie(response, result.access_token, result.expires_at)
        _set_csrf_cookie(response)
    return response


@router.get("/me", response_model=AccountView)
def get_me(principal: Principal, request: Request) -> AccountView:
    if principal.account_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid principal")
    try:
        account = request.app.state.account_repository.get(principal.account_id)
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid principal"
        ) from error
    return request.app.state.auth_service.view(account)


@router.post("/change-password", response_model=LoginResponse)
def change_password(
    request: ChangePasswordRequest,
    principal: Principal,
    http_request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    session_cookie: str | None = Cookie(default=None, alias="study_session"),
) -> JSONResponse:
    if principal.account_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid principal")
    try:
        account = http_request.app.state.account_repository.get(principal.account_id)
        result = http_request.app.state.auth_service.change_password(
            account, request.current_password, request.new_password
        )
    except (AuthError, PasswordPolicyError, LookupError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials"
        ) from error
    # Browser callers keep the rotated token in HttpOnly storage; Flutter gets
    # the token in the response and stores it in Keychain/Keystore.
    browser_call = (
        session_cookie is not None and _token(authorization, session_cookie) == session_cookie
    )
    body = result.model_copy(update={"access_token": None}) if browser_call else result
    response = JSONResponse(status_code=status.HTTP_200_OK, content=body.model_dump(mode="json"))
    if browser_call:
        _set_session_cookie(response, result.access_token, result.expires_at)
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    principal: Principal,
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    session_cookie: str | None = Cookie(default=None, alias="study_session"),
) -> Response:
    token = _token(authorization, session_cookie)
    if token:
        try:
            _, session = request.app.state.auth_service.authenticate(token)
            request.app.state.auth_service.logout(session)
        except AuthError:
            pass
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie("study_session", path="/")
    response.delete_cookie("study_csrf", path="/")
    return response


@router.get("/households/{household_id}/accounts", response_model=list[AccountView])
def list_accounts(household_id: UUID, principal: Principal, request: Request) -> list[AccountView]:
    require_parent(require_household(principal, household_id))
    owned_child_ids = {
        child.id
        for child in request.app.state.profile_repository.list_children(
            household_id, owner_account_id=principal.account_id
        )
    }
    return [
        request.app.state.auth_service.view(item)
        for item in request.app.state.account_repository.list_household(household_id)
        if item.id == principal.account_id or item.child_id in owned_child_ids
    ]


@router.post(
    "/households/{household_id}/accounts/children",
    response_model=AccountView,
    status_code=status.HTTP_201_CREATED,
)
def create_child_account(
    household_id: UUID,
    body: CreateChildAccountRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    request: Request,
) -> JSONResponse:
    require_parent(require_household(principal, household_id))
    # Account creation must bind to an existing profile in this household. The
    # repository method is intentionally not trusted to infer this boundary
    # from an arbitrary UUID supplied by the caller.
    _require_owned_child(principal, request, household_id, body.child_id)
    try:
        account, replayed = request.app.state.auth_service.create_child_account(
            household_id, body, idempotency_key
        )
    except DuplicateUsernameError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="username already exists"
        ) from error
    except (IdempotencyConflictError, ValueError, PasswordPolicyError) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="account cannot be created"
        ) from error
    return JSONResponse(
        status_code=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        content=account.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


@router.post(
    "/households/{household_id}/accounts/parents",
    response_model=AccountView,
    status_code=status.HTTP_201_CREATED,
)
def create_parent_account(
    household_id: UUID,
    body: CreateParentAccountRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    request: Request,
) -> JSONResponse:
    require_super_admin(principal.role)
    try:
        account, replayed = request.app.state.auth_service.create_parent_account(
            household_id, body, idempotency_key
        )
    except DuplicateUsernameError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="username already exists"
        ) from error
    except (IdempotencyConflictError, ValueError, PasswordPolicyError) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="account cannot be created"
        ) from error
    return JSONResponse(
        status_code=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        content=account.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


@router.post("/households", response_model=AccountView, status_code=status.HTTP_201_CREATED)
def provision_household(
    body: CreateHouseholdRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    request: Request,
) -> JSONResponse:
    """Let the instance super administrator provision an isolated family."""

    require_super_admin(principal.role)
    try:
        account, replayed = request.app.state.auth_service.provision_household(
            body, idempotency_key
        )
    except DuplicateUsernameError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="username already exists"
        ) from error
    except (IdempotencyConflictError, ValueError, PasswordPolicyError) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="household cannot be created"
        ) from error
    return JSONResponse(
        status_code=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        content=account.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


@router.get("/family-parents", response_model=list[FamilyParentView])
def list_family_parents(principal: Principal, request: Request) -> list[FamilyParentView]:
    """List ordinary family parents for the instance super administrator only."""

    require_super_admin(principal.role)
    return request.app.state.auth_service.list_family_parents(request.app.state.profile_repository)


@router.delete("/family-parents/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_family_parent(
    account_id: UUID,
    body: DeleteParentAccountRequest,
    principal: Principal,
    request: Request,
) -> Response:
    require_super_admin(principal.role)
    _require_parent_reauth(principal, request, body.current_password)
    try:
        account = request.app.state.account_repository.get(account_id)
        if account.role is not AccountRole.PARENT:
            raise LookupError
        if request.app.state.profile_repository.list_children(
            account.household_id, owner_account_id=account.id
        ):
            raise ValueError("parent still owns children")
        request.app.state.auth_service.delete_parent_account(account_id)
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="resource not found"
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="parent account still owns children",
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/households/{household_id}/accounts/{account_id}/status", response_model=AccountView)
def set_account_status(
    household_id: UUID,
    account_id: UUID,
    body: SetAccountStatusRequest,
    principal: Principal,
    request: Request,
) -> AccountView:
    require_parent(require_household(principal, household_id))
    _require_parent_reauth(principal, request, body.current_password)
    try:
        account = request.app.state.account_repository.get(account_id)
        if account.household_id != household_id or account.role is not AccountRole.CHILD:
            raise LookupError
        _require_owned_child(principal, request, household_id, account.child_id)
        return request.app.state.auth_service.set_status(account_id, body.enabled)
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="resource not found"
        ) from error


@router.post(
    "/households/{household_id}/accounts/{account_id}/reset-password", response_model=AccountView
)
def reset_account_password(
    household_id: UUID,
    account_id: UUID,
    body: ResetPasswordRequest,
    principal: Principal,
    request: Request,
) -> AccountView:
    require_parent(require_household(principal, household_id))
    _require_parent_reauth(principal, request, body.current_password)
    try:
        account = request.app.state.account_repository.get(account_id)
        if account.household_id != household_id or account.role is not AccountRole.CHILD:
            raise LookupError
        _require_owned_child(principal, request, household_id, account.child_id)
        return request.app.state.auth_service.reset_password(account_id, body.new_password)
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="resource not found"
        ) from error
    except PasswordPolicyError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="password reset failed"
        ) from error
