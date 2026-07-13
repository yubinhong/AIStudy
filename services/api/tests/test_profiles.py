from uuid import UUID

from fastapi.testclient import TestClient

from study_api.main import create_app

HOUSEHOLD_A = "00000000-0000-0000-0000-000000000001"
HOUSEHOLD_B = "00000000-0000-0000-0000-000000000002"
CHILD_A = "00000000-0000-0000-0000-000000000101"


def principal(household_id: str = HOUSEHOLD_A, role: str = "parent") -> dict[str, str]:
    return {"X-Demo-Household-Id": household_id, "X-Demo-Role": role}


def test_parent_can_list_only_children_in_own_household() -> None:
    client = TestClient(create_app())

    response = client.get(f"/households/{HOUSEHOLD_A}/children", headers=principal())

    assert response.status_code == 200
    assert [child["id"] for child in response.json()] == [CHILD_A]


def test_cross_household_reads_are_not_enumerable() -> None:
    client = TestClient(create_app())

    response = client.get(f"/households/{HOUSEHOLD_B}/children", headers=principal())
    child_response = client.get(
        f"/households/{HOUSEHOLD_A}/children/{UUID('00000000-0000-0000-0000-000000000102')}",
        headers=principal(),
    )

    assert response.status_code == 404
    assert response.json() == {"code": "HTTP_404", "message": "resource not found"}
    assert child_response.status_code == 404


def test_child_creation_is_idempotent_and_detects_payload_reuse() -> None:
    client = TestClient(create_app())
    payload = {
        "display_name": "Synthetic New Child",
        "grade": 2,
        "curriculum_version": "math-demo-2026",
        "subjects": ["math"],
    }
    headers = {**principal(), "Idempotency-Key": "child-create-001"}

    first = client.post(f"/households/{HOUSEHOLD_A}/children", json=payload, headers=headers)
    replay = client.post(f"/households/{HOUSEHOLD_A}/children", json=payload, headers=headers)
    conflict = client.post(
        f"/households/{HOUSEHOLD_A}/children",
        json={**payload, "grade": 3},
        headers=headers,
    )

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.json() == first.json()
    assert conflict.status_code == 409


def test_only_parent_can_create_and_list_devices() -> None:
    client = TestClient(create_app())
    payload = {"kind": "child", "platform": "ios", "display_name": "Synthetic iPad 2"}
    headers = {**principal(), "Idempotency-Key": "device-create-001"}

    child_create = client.post(
        f"/households/{HOUSEHOLD_A}/devices",
        json=payload,
        headers={**principal(role="child"), "Idempotency-Key": "device-child-001"},
    )
    parent_create = client.post(f"/households/{HOUSEHOLD_A}/devices", json=payload, headers=headers)
    parent_list = client.get(f"/households/{HOUSEHOLD_A}/devices", headers=principal())

    assert child_create.status_code == 403
    assert child_create.json() == {"code": "HTTP_403", "message": "parent role required"}
    assert parent_create.status_code == 201
    assert parent_list.status_code == 200
    assert any(device["id"] == parent_create.json()["id"] for device in parent_list.json())


def test_missing_principal_is_rejected() -> None:
    client = TestClient(create_app())

    response = client.get(f"/households/{HOUSEHOLD_A}/children")

    assert response.status_code == 401
