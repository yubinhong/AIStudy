from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from study_api.auth_domain import (
    BOOTSTRAP_PASSWORD,
    AuthError,
    AuthService,
    CreateChildAccountRequest,
    InMemoryAccountRepository,
    LoginRequest,
)
from study_api.main import create_app

HOUSEHOLD_A = "00000000-0000-0000-0000-000000000001"
CHILD_A = UUID("00000000-0000-0000-0000-000000000101")


def test_household_routes_reject_removed_demo_and_unsigned_bearer_credentials() -> None:
    client = TestClient(create_app())

    demo = client.get(
        f"/households/{HOUSEHOLD_A}/children",
        headers={
            "X-Demo-Household-Id": HOUSEHOLD_A,
            "X-Demo-Role": "parent",
        },
    )
    unsigned = client.get(
        f"/households/{HOUSEHOLD_A}/children",
        headers={"Authorization": "Bearer st1.removed-legacy-token"},
    )

    assert demo.status_code == 401
    assert unsigned.status_code == 401


def test_bootstrap_requires_local_first_login_and_data_is_blocked_until_change() -> None:
    app = create_app()
    service = app.state.auth_service
    bootstrap = service.login(
        LoginRequest(username="admin", password=BOOTSTRAP_PASSWORD, client="flutter"),
        remote_host="127.0.0.1",
    )
    token = bootstrap.access_token
    assert token is not None
    client = TestClient(app, client=("127.0.0.1", 50000))

    blocked = client.get(
        f"/households/{HOUSEHOLD_A}/children",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["message"] == "password change required"

    changed = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": BOOTSTRAP_PASSWORD, "new_password": "a-secure-parent-password"},
    )
    assert changed.status_code == 200
    new_token = changed.json()["access_token"]
    assert new_token and new_token != token

    accessible = client.get(
        f"/households/{HOUSEHOLD_A}/children",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert accessible.status_code == 200

    logged_out = client.post("/auth/logout", headers={"Authorization": f"Bearer {new_token}"})
    assert logged_out.status_code == 204
    revoked = client.get(
        f"/households/{HOUSEHOLD_A}/children",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert revoked.status_code == 401


def test_child_account_login_is_bound_to_one_child_and_can_be_disabled() -> None:
    app = create_app()
    service = app.state.auth_service
    parent = service.login(
        LoginRequest(username="admin", password=BOOTSTRAP_PASSWORD, client="flutter"),
        remote_host="127.0.0.1",
    )
    service.change_password(
        app.state.account_repository.get(parent.account.id),
        BOOTSTRAP_PASSWORD,
        "a-secure-parent-password",
    )
    account, _ = service.create_child_account(
        UUID(HOUSEHOLD_A),
        CreateChildAccountRequest(username="child-a", password="child-pass-123", child_id=CHILD_A),
        "child-account-001",
    )
    client = TestClient(app)

    login = client.post(
        "/auth/login",
        json={"username": "child-a", "password": "child-pass-123", "client": "flutter"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert login.json()["account"]["child_id"] == str(CHILD_A)

    service.set_status(account.id, False)
    disabled = client.get(
        f"/households/{HOUSEHOLD_A}/tasks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert disabled.status_code == 401


def test_child_account_creation_rejects_profile_from_another_household() -> None:
    app = create_app()
    service = app.state.auth_service
    parent = service.login(
        LoginRequest(username="admin", password=BOOTSTRAP_PASSWORD, client="flutter"),
        remote_host="127.0.0.1",
    )
    service.change_password(
        app.state.account_repository.get(parent.account.id),
        BOOTSTRAP_PASSWORD,
        "a-secure-parent-password",
    )
    client = TestClient(app)
    token = service.login(
        LoginRequest(username="admin", password="a-secure-parent-password", client="flutter"),
        remote_host="127.0.0.1",
    ).access_token
    response = client.post(
        f"/auth/households/{HOUSEHOLD_A}/accounts/children",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "cross-child-001"},
        json={
            "username": "wrong-child",
            "password": "child-pass-123",
            "child_id": "00000000-0000-0000-0000-000000000102",
        },
    )
    assert response.status_code == 404


def test_five_failed_password_attempts_lock_account() -> None:
    repository = InMemoryAccountRepository()
    service = AuthService(repository)
    for _ in range(5):
        with pytest.raises(AuthError):
            service.login(
                LoginRequest(username="admin", password="wrong-password", client="flutter"),
                remote_host="127.0.0.1",
            )
    with pytest.raises(AuthError):
        service.login(
            LoginRequest(username="admin", password=BOOTSTRAP_PASSWORD, client="flutter"),
            remote_host="127.0.0.1",
        )

    events = repository.audit_events
    assert [event.event_name for event in events] == [
        "auth_login_failed",
        "auth_login_failed",
        "auth_login_failed",
        "auth_login_failed",
        "auth_login_failed",
        "auth_account_locked",
        "auth_login_blocked",
    ]
    serialized = " ".join(event.model_dump_json() for event in events)
    assert BOOTSTRAP_PASSWORD not in serialized
    assert "wrong-password" not in serialized


def test_auth_audit_records_successful_lifecycle_without_credentials() -> None:
    repository = InMemoryAccountRepository()
    service = AuthService(repository)
    login = service.login(
        LoginRequest(username="admin", password=BOOTSTRAP_PASSWORD, client="flutter"),
        remote_host="127.0.0.1",
    )
    assert login.access_token is not None
    changed = service.change_password(
        repository.get(login.account.id), BOOTSTRAP_PASSWORD, "a-secure-parent-password"
    )
    assert changed.access_token is not None
    _, session = service.authenticate(changed.access_token)
    service.logout(session)

    assert [event.event_name for event in repository.audit_events] == [
        "auth_login_succeeded",
        "auth_password_changed",
        "auth_logout",
    ]
    assert all(
        event.resource_id != UUID("00000000-0000-0000-0000-000000000000")
        for event in repository.audit_events
    )


def test_web_session_uses_cookie_and_requires_csrf_for_mutations() -> None:
    app = create_app()
    client = TestClient(app, client=("127.0.0.1", 50000))
    login = client.post(
        "/auth/login",
        json={"username": "admin", "password": BOOTSTRAP_PASSWORD, "client": "web"},
    )
    assert login.status_code == 200
    assert login.json()["access_token"] is None
    csrf = client.cookies.get("study_csrf")
    assert csrf

    blocked = client.post(
        "/auth/change-password",
        json={"current_password": BOOTSTRAP_PASSWORD, "new_password": "a-secure-parent-password"},
    )
    assert blocked.status_code == 403

    changed = client.post(
        "/auth/change-password",
        headers={"X-CSRF-Token": csrf},
        json={"current_password": BOOTSTRAP_PASSWORD, "new_password": "a-secure-parent-password"},
    )
    assert changed.status_code == 200
    assert changed.json()["access_token"] is None
    assert client.get("/auth/me").status_code == 200


def test_parent_reauthentication_is_required_for_child_account_management() -> None:
    app = create_app()
    service = app.state.auth_service
    bootstrap = service.login(
        LoginRequest(username="admin", password=BOOTSTRAP_PASSWORD, client="flutter"),
        remote_host="127.0.0.1",
    )
    changed = service.change_password(
        app.state.account_repository.get(bootstrap.account.id),
        BOOTSTRAP_PASSWORD,
        "a-secure-parent-password",
    )
    child, _ = service.create_child_account(
        UUID(HOUSEHOLD_A),
        CreateChildAccountRequest(username="child-a", password="child-pass-123", child_id=CHILD_A),
        "child-account-002",
    )
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {changed.access_token}"}
    invalid = client.patch(
        f"/auth/households/{HOUSEHOLD_A}/accounts/{child.id}/status",
        headers=headers,
        json={"enabled": False, "current_password": "wrong-password"},
    )
    assert invalid.status_code == 401
    disabled = client.patch(
        f"/auth/households/{HOUSEHOLD_A}/accounts/{child.id}/status",
        headers=headers,
        json={"enabled": False, "current_password": "a-secure-parent-password"},
    )
    assert disabled.status_code == 200
    reset = client.post(
        f"/auth/households/{HOUSEHOLD_A}/accounts/{child.id}/reset-password",
        headers=headers,
        json={
            "current_password": "a-secure-parent-password",
            "new_password": "child-pass-456",
        },
    )
    assert reset.status_code == 200
