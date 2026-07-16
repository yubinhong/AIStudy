"""Password-login helpers for API route tests.

Tests establish the same revocable sessions as production callers. They do not
override the FastAPI dependency or synthesize authorization principals.
"""

from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient

from study_api.auth_domain import (
    BOOTSTRAP_PASSWORD,
    BOOTSTRAP_USERNAME,
    CreateChildAccountRequest,
    LoginRequest,
)

DEFAULT_HOUSEHOLD_ID = UUID("00000000-0000-0000-0000-000000000001")
PARENT_PASSWORD = "test-parent-password"
CHILD_INITIAL_PASSWORD = "child-pass-123"
CHILD_PASSWORD = "child-pass-456"


def session_headers(
    client: TestClient,
    *,
    role: str = "parent",
    household_id: str | UUID = DEFAULT_HOUSEHOLD_ID,
    child_id: str | UUID | None = None,
) -> dict[str, str]:
    """Return an opaque session created through the password-account domain."""

    household = UUID(str(household_id))
    child = UUID(str(child_id)) if child_id is not None else None
    key = (role, household, child)
    cache: dict[tuple[str, UUID, UUID | None], str] = getattr(
        client, "_study_test_session_tokens", {}
    )
    if key not in cache:
        cache[key] = (
            _parent_token(client, household)
            if role == "parent"
            else _child_token(client, household, child)
        )
        client._study_test_session_tokens = cache
    return {"Authorization": f"Bearer {cache[key]}"}


def _parent_token(client: TestClient, household_id: UUID) -> str:
    if household_id != DEFAULT_HOUSEHOLD_ID:
        raise ValueError("route tests only bootstrap a parent in the default Household")
    service = _app_state(client).auth_service
    repository = _app_state(client).account_repository
    account = repository.get_by_username(BOOTSTRAP_USERNAME)
    if account is None:
        raise AssertionError("bootstrap parent account is missing")
    if account.must_change_password:
        initial = service.login(
            LoginRequest(
                username=BOOTSTRAP_USERNAME,
                password=BOOTSTRAP_PASSWORD,
                client="flutter",
            ),
            remote_host="127.0.0.1",
        )
        result = service.change_password(
            repository.get(initial.account.id), BOOTSTRAP_PASSWORD, PARENT_PASSWORD
        )
    else:
        result = service.login(
            LoginRequest(
                username=BOOTSTRAP_USERNAME,
                password=PARENT_PASSWORD,
                client="flutter",
            ),
            remote_host="127.0.0.1",
        )
    if result.access_token is None:
        raise AssertionError("parent session token is missing")
    return result.access_token


def _child_token(client: TestClient, household_id: UUID, child_id: UUID | None) -> str:
    if child_id is None:
        raise ValueError("child route tests require an account-bound child id")
    service = _app_state(client).auth_service
    repository = _app_state(client).account_repository
    username = f"test-child-{household_id.hex[-8:]}-{child_id.hex[-8:]}"
    account = repository.get_by_username(username)
    if account is None:
        created, _ = service.create_child_account(
            household_id,
            CreateChildAccountRequest(
                username=username,
                password=CHILD_INITIAL_PASSWORD,
                child_id=child_id,
            ),
            f"create-{household_id.hex[-8:]}-{child_id.hex[-8:]}",
        )
        account = repository.get(created.id)
    password = CHILD_INITIAL_PASSWORD if account.must_change_password else CHILD_PASSWORD
    initial = service.login(
        LoginRequest(username=username, password=password, client="flutter"),
        remote_host="127.0.0.1",
    )
    result = (
        service.change_password(account, CHILD_INITIAL_PASSWORD, CHILD_PASSWORD)
        if account.must_change_password
        else initial
    )
    if result.access_token is None:
        raise AssertionError("child session token is missing")
    return result.access_token


def _app_state(client: TestClient) -> Any:
    return client.app.state  # type: ignore[union-attr]
