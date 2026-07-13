"""Local-only synthetic principal and Household boundary checks."""

from dataclasses import dataclass
from uuid import UUID

from fastapi import Header, HTTPException, status

from study_api.domain.models import DemoRole


@dataclass(frozen=True)
class DemoPrincipal:
    """Synthetic local/CI principal; it is never a production identity."""

    household_id: UUID
    role: DemoRole
    child_id: UUID | None


def get_demo_principal(
    household_header: str | None = Header(default=None, alias="X-Demo-Household-Id"),
    role_header: str | None = Header(default=None, alias="X-Demo-Role"),
    child_header: str | None = Header(default=None, alias="X-Demo-Child-Id"),
) -> DemoPrincipal:
    """Read a synthetic local/CI principal; never use this as production auth."""

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
