"""Account-session authentication and Household authorization checks."""

from dataclasses import dataclass
from hmac import compare_digest
from uuid import UUID

from fastapi import Cookie, Header, HTTPException, Request, status

from study_api.domain.models import AccountRole


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """A Household principal authenticated by a revocable account session."""

    household_id: UUID
    role: AccountRole
    child_id: UUID | None
    account_id: UUID
    session_id: UUID
    must_change_password: bool = False


def get_principal(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    session_cookie: str | None = Cookie(default=None, alias="study_session"),
    csrf_cookie: str | None = Cookie(default=None, alias="study_csrf"),
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> AuthenticatedPrincipal:
    """Authenticate one opaque session from a Cookie or Bearer transport."""

    token = session_cookie or _bearer_token(authorization)
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="principal required")

    try:
        account, session = request.app.state.auth_service.authenticate(token)
    except Exception as error:  # noqa: BLE001 -- keep all session failures indistinguishable.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid principal"
        ) from error

    if account.must_change_password and not (
        request.url.path.startswith("/auth/change-password")
        or request.url.path.startswith("/auth/logout")
        or request.url.path.startswith("/auth/me")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="password change required"
        )

    if session_cookie is not None and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if not csrf_cookie or not csrf_header or not compare_digest(csrf_cookie, csrf_header):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="csrf token required")

    return AuthenticatedPrincipal(
        household_id=account.household_id,
        role=account.role,
        child_id=account.child_id,
        account_id=account.id,
        session_id=session.id,
        must_change_password=account.must_change_password,
    )


def _bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token.strip():
        return None
    return token.strip()


def require_household(principal: AuthenticatedPrincipal, household_id: UUID) -> AccountRole:
    """Return the role only when the path Household belongs to the principal."""

    if principal.household_id != household_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    return principal.role


def require_parent(role: AccountRole) -> None:
    if role is not AccountRole.PARENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="parent role required")


def require_bound_child(principal: AuthenticatedPrincipal) -> UUID:
    """Require the account to be bound to one child profile."""

    if principal.role is not AccountRole.CHILD or principal.child_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="bound child principal required"
        )
    return principal.child_id
