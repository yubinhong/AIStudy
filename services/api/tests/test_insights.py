from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from auth_helpers import session_headers
from fastapi.testclient import TestClient

from study_api.domain.insights_repository import (
    ChildDataExport,
    EmptyInsightsRepository,
    LearningDetail,
)
from study_api.domain.models import ChildProfile, Subject
from study_api.main import create_app

HOUSEHOLD_A = "00000000-0000-0000-0000-000000000001"
CHILD_A = "00000000-0000-0000-0000-000000000101"
CHILD_B = "00000000-0000-0000-0000-000000000102"


class ExportInsightsRepository(EmptyInsightsRepository):
    def __init__(self) -> None:
        self._exports: dict[str, ChildDataExport] = {}

    def export_child(
        self,
        household_id: UUID,
        child_id: UUID,
        idempotency_key: str,
    ) -> tuple[ChildDataExport, bool]:
        replayed = idempotency_key in self._exports
        export = self._exports.get(idempotency_key)
        if export is None:
            export = ChildDataExport(
                generated_at=datetime(2026, 7, 17, tzinfo=UTC),
                child=ChildProfile(
                    id=child_id,
                    household_id=household_id,
                    owner_account_id=UUID("00000000-0000-0000-0000-000000000001"),
                    display_name="Synthetic Child A",
                    grade=3,
                    curriculum_version="math-demo-2026",
                    subjects=[Subject.MATH],
                    created_at=datetime(2026, 1, 1, tzinfo=UTC),
                ),
                tasks=(),
                sessions=(),
                attempts=(),
                verified_questions=(),
                tutor_turns=(),
            )
            self._exports[idempotency_key] = export
        return export, replayed


class RecordingInsightsRepository(EmptyInsightsRepository):
    def __init__(self) -> None:
        self.calls: list[tuple[datetime, datetime, int]] = []

    def learning_details(
        self,
        household_id: UUID,
        child_id: UUID,
        *,
        from_at: datetime,
        to_at: datetime,
        limit: int = 200,
    ) -> tuple[LearningDetail, ...]:
        del household_id, child_id
        self.calls.append((from_at, to_at, limit))
        return ()


def test_weekly_report_is_household_and_child_scoped_without_content() -> None:
    client = TestClient(create_app(insights_repository=EmptyInsightsRepository()))
    week_start = date.today() - timedelta(days=date.today().weekday())
    path = (
        f"/households/{HOUSEHOLD_A}/reports/weekly"
        f"?child_id={CHILD_A}&week_start={week_start.isoformat()}"
    )

    child = client.get(
        path,
        headers=session_headers(client, role="child", child_id=CHILD_A),
    )
    sibling = client.get(
        path,
        headers=session_headers(client, role="child", child_id=CHILD_B),
    )

    assert child.status_code == 200
    assert child.json()["child_id"] == CHILD_A
    assert child.json()["completion_rate"] == 0
    assert "question_text" not in child.text
    assert "answer" not in child.text
    assert sibling.status_code == 404


def test_weekly_report_rejects_unknown_profile() -> None:
    client = TestClient(create_app(insights_repository=EmptyInsightsRepository()))
    response = client.get(
        f"/households/{HOUSEHOLD_A}/reports/weekly?child_id={UUID(int=999)}&week_start=2026-07-13",
        headers=session_headers(client, role="parent"),
    )
    assert response.status_code == 404


def test_parent_learning_details_are_scoped_and_children_cannot_read_them() -> None:
    client = TestClient(create_app(insights_repository=EmptyInsightsRepository()))
    path = f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/learning-details"

    parent = client.get(path, headers=session_headers(client, role="parent"))
    child = client.get(
        path,
        headers=session_headers(client, role="child", child_id=CHILD_A),
    )

    assert parent.status_code == 200
    assert parent.json() == []
    assert child.status_code == 403


def test_learning_details_default_to_a_bounded_30_day_window() -> None:
    repository = RecordingInsightsRepository()
    client = TestClient(create_app(insights_repository=repository))

    response = client.get(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/learning-details",
        headers=session_headers(client, role="parent"),
    )

    assert response.status_code == 200
    assert len(repository.calls) == 1
    from_at, to_at, limit = repository.calls[0]
    assert to_at - from_at == timedelta(days=30)
    assert from_at.tzinfo is UTC
    assert to_at.tzinfo is UTC
    assert limit == 200


def test_learning_details_accept_one_timezone_aware_day_and_normalizes_to_utc() -> None:
    repository = RecordingInsightsRepository()
    client = TestClient(create_app(insights_repository=repository))
    query = "from_at=2026-07-29T00:00:00%2B08:00&to_at=2026-07-30T00:00:00%2B08:00"

    response = client.get(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/learning-details?{query}&limit=500",
        headers=session_headers(client, role="parent"),
    )

    assert response.status_code == 200
    from_at, to_at, limit = repository.calls[0]
    assert from_at == datetime(2026, 7, 28, 16, tzinfo=UTC)
    assert to_at == datetime(2026, 7, 29, 16, tzinfo=UTC)
    assert limit == 500


def test_learning_details_reject_invalid_or_expired_ranges() -> None:
    client = TestClient(create_app(insights_repository=RecordingInsightsRepository()))
    headers = session_headers(client, role="parent")
    path = f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/learning-details"

    reversed_range = client.get(
        f"{path}?from_at=2026-07-30T00:00:00Z&to_at=2026-07-29T00:00:00Z",
        headers=headers,
    )
    expired = client.get(
        f"{path}?from_at=2025-01-01T00:00:00Z&to_at=2025-01-02T00:00:00Z",
        headers=headers,
    )

    assert reversed_range.status_code == 422
    assert reversed_range.json()["message"] == "from_at must be before to_at"
    assert expired.status_code == 422
    assert expired.json()["message"] == "learning history is retained for 180 days"


def test_parent_can_export_child_data_with_exact_idempotent_replay() -> None:
    client = TestClient(create_app(insights_repository=ExportInsightsRepository()))
    path = f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/exports"
    headers = {
        **session_headers(client, role="parent"),
        "Idempotency-Key": "synthetic-export-key",
    }

    created = client.post(path, headers=headers)
    replayed = client.post(path, headers=headers)

    assert created.status_code == 200
    assert replayed.status_code == 200
    assert replayed.headers["Idempotency-Replayed"] == "true"
    assert replayed.json() == created.json()
    assert "password" not in created.text
    assert "object_key" not in created.text


def test_child_cannot_export_data() -> None:
    client = TestClient(create_app(insights_repository=ExportInsightsRepository()))
    response = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/exports",
        headers={
            **session_headers(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": "synthetic-export-key",
        },
    )
    assert response.status_code == 403
