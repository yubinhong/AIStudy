"""Household boundary checks with a self-hosted bearer mode."""

import os
from dataclasses import dataclass
from uuid import UUID

from fastapi import Header, HTTPException, status

from study_api.auth_tokens import AuthTokenError, parse_token
from study_api.domain.models import DemoRole


@dataclass(frozen=True)
class DemoPrincipal:
    """Synthetic local/CI principal; it is never a production identity."""

    household_id: UUID
    role: DemoRole
    child_id: UUID | None


def get_demo_principal(
    authorization: str | None = Header(default=None, alias="Authorization"),
    household_header: str | None = Header(default=None, alias="X-Demo-Household-Id"),
    role_header: str | None = Header(default=None, alias="X-Demo-Role"),
    child_header: str | None = Header(default=None, alias="X-Demo-Child-Id"),
) -> DemoPrincipal:
    """Read self-hosted bearer auth, or local demo headers in compatibility mode."""

    if authorization is not None:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid principal"
            )
        secret = os.environ.get("STUDY_AUTH_SECRET", "")
        try:
            claims = parse_token(secret, token)
        except AuthTokenError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid principal"
            ) from error
        return DemoPrincipal(claims.household_id, claims.role, claims.child_id)

    if os.environ.get("STUDY_AUTH_MODE", "demo").lower() == "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="principal required")

    if household_header is None or role_header is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="principal required")
    try:
        household_id = UUID(household_header)
        role = DemoRole(role_header)
        child_id = UUID(child_header) if child_header is not None else None
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid principal"
        ) from error
    return DemoPrincipal(household_id=household_id, role=role, child_id=child_id)


def require_household(principal: DemoPrincipal, household_id: UUID) -> DemoRole:
    """Return role only when the path Household belongs to the principal."""

    if principal.household_id != household_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    return principal.role


def require_parent(role: DemoRole) -> None:
    if role is not DemoRole.PARENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="parent role required")


def require_bound_child(principal: DemoPrincipal) -> UUID:
    """Require a synthetic child binding for child-only learning operations."""

    if principal.role is not DemoRole.CHILD or principal.child_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="bound child principal required"
        )
    return principal.child_id
