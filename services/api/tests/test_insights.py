from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from auth_helpers import session_headers
from fastapi.testclient import TestClient

from study_api.domain.insights_repository import ChildDataExport, EmptyInsightsRepository
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
