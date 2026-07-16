from uuid import UUID

from auth_helpers import session_headers
from fastapi.testclient import TestClient

from study_api.main import create_app
from study_api.media_lifecycle import CaptureObject, DeletionStatus

HOUSEHOLD_A = "00000000-0000-0000-0000-000000000001"
HOUSEHOLD_B = "00000000-0000-0000-0000-000000000002"
CHILD_A = "00000000-0000-0000-0000-000000000101"
CHILD_B = "00000000-0000-0000-0000-000000000102"


def principal(
    client: TestClient, household_id: str = HOUSEHOLD_A, role: str = "parent"
) -> dict[str, str]:
    child_id = (CHILD_A if household_id == HOUSEHOLD_A else CHILD_B) if role == "child" else None
    return session_headers(client, role=role, household_id=household_id, child_id=child_id)


def test_parent_can_list_only_children_in_own_household() -> None:
    client = TestClient(create_app())

    response = client.get(f"/households/{HOUSEHOLD_A}/children", headers=principal(client))

    assert response.status_code == 200
    assert [child["id"] for child in response.json()] == [CHILD_A]


def test_cross_household_reads_are_not_enumerable() -> None:
    client = TestClient(create_app())

    response = client.get(f"/households/{HOUSEHOLD_B}/children", headers=principal(client))
    child_response = client.get(
        f"/households/{HOUSEHOLD_A}/children/{UUID('00000000-0000-0000-0000-000000000102')}",
        headers=principal(client),
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
    headers = {**principal(client), "Idempotency-Key": "child-create-001"}

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
    headers = {**principal(client), "Idempotency-Key": "device-create-001"}

    child_create = client.post(
        f"/households/{HOUSEHOLD_A}/devices",
        json=payload,
        headers={**principal(client, role="child"), "Idempotency-Key": "device-child-001"},
    )
    parent_create = client.post(f"/households/{HOUSEHOLD_A}/devices", json=payload, headers=headers)
    parent_list = client.get(f"/households/{HOUSEHOLD_A}/devices", headers=principal(client))

    assert child_create.status_code == 403
    assert child_create.json() == {"code": "HTTP_403", "message": "parent role required"}
    assert parent_create.status_code == 201
    assert parent_list.status_code == 200
    assert any(device["id"] == parent_create.json()["id"] for device in parent_list.json())


def test_missing_principal_is_rejected() -> None:
    client = TestClient(create_app())

    response = client.get(f"/households/{HOUSEHOLD_A}/children")

    assert response.status_code == 401


class FakeChildDeleteRepository:
    def __init__(self) -> None:
        self.item = CaptureObject(UUID(int=91), "captures/synthetic/profile-delete")
        self.status = DeletionStatus.ACTIVE

    def claim_child_capture_objects(
        self, household_id: UUID, child_id: UUID
    ) -> list[CaptureObject]:
        assert household_id == UUID(HOUSEHOLD_A)
        assert child_id == UUID(CHILD_A)
        if self.status not in {DeletionStatus.ACTIVE, DeletionStatus.FAILED}:
            return []
        self.status = DeletionStatus.DELETING
        return [self.item]

    def mark_capture_deleted(self, capture_id: UUID) -> None:
        assert capture_id == self.item.capture_id
        self.status = DeletionStatus.DELETED

    def mark_capture_deletion_failed(self, capture_id: UUID) -> None:
        assert capture_id == self.item.capture_id
        self.status = DeletionStatus.FAILED


class FakeChildDeleteStorage:
    def __init__(self) -> None:
        self.fail = True
        self.deleted: list[str] = []

    def delete_object(self, object_key: str) -> None:
        self.deleted.append(object_key)
        if self.fail:
            raise RuntimeError("synthetic deletion failure")


def test_parent_child_delete_keeps_profile_until_media_cascade_succeeds() -> None:
    repository = FakeChildDeleteRepository()
    storage = FakeChildDeleteStorage()
    client = TestClient(create_app(capture_repository=repository, object_storage=storage))
    headers = {**principal(client), "Idempotency-Key": "child-delete-001"}
    path = f"/households/{HOUSEHOLD_A}/children/{CHILD_A}"

    failed = client.delete(path, headers=headers)
    still_present = client.get(path, headers=principal(client))

    storage.fail = False
    deleted = client.delete(path, headers=headers)
    replay = client.delete(path, headers=headers)
    missing = client.get(path, headers=principal(client))

    assert failed.status_code == 503
    assert failed.json() == {
        "code": "HTTP_503",
        "message": "child deletion is incomplete and can be retried",
    }
    assert still_present.status_code == 200
    assert deleted.status_code == 204
    assert replay.status_code == 204
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert missing.status_code == 404
    assert repository.status is DeletionStatus.DELETED
    assert storage.deleted == ["captures/synthetic/profile-delete"] * 2


def test_child_or_cross_household_cannot_delete_profile() -> None:
    client = TestClient(create_app())
    path = f"/households/{HOUSEHOLD_A}/children/{CHILD_A}"

    child = client.delete(
        path,
        headers={
            **principal(client, role="child"),
            "Idempotency-Key": "child-delete-role",
        },
    )
    other_household = client.delete(
        path,
        headers={
            **principal(client, HOUSEHOLD_B, "child"),
            "Idempotency-Key": "child-delete-household",
        },
    )

    assert child.status_code == 403
    assert other_household.status_code == 404
