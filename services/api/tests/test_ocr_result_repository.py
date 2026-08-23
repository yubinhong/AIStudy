from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest
from auth_helpers import session_headers
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from study_api.domain.learning_repository import ChildAssignmentError
from study_api.domain.models import OcrResultStatus
from study_api.domain.ocr_result_repository import (
    OcrResultDraft,
    PostgresOcrResultRepository,
)
from study_api.domain.repository import IdempotencyConflictError, InMemoryProfileRepository
from study_api.domain.sql_capture_repository import PostgresCaptureRepository
from study_api.domain.sql_learning_repository import PostgresLearningRepository
from study_api.main import create_app
from study_api.ocr_provider import parse_paddle_text_result

HOUSEHOLD_A = UUID("00000000-0000-0000-0000-000000000001")
HOUSEHOLD_B = UUID("00000000-0000-0000-0000-000000000002")
CHILD_A = UUID("00000000-0000-0000-0000-000000000101")
CHILD_B = UUID("00000000-0000-0000-0000-000000000102")


def test_ocr_result_draft_normalizes_parser_output_and_keeps_manual_gate() -> None:
    parsed = parse_paddle_text_result({"rec_texts": ["  12 + 3  ", ""], "rec_scores": [0.94, 0.3]})
    draft = OcrResultDraft.from_parse_result(parsed)

    assert draft.status is OcrResultStatus.CANDIDATE
    assert draft.confidence == 0.94
    assert draft.requires_manual_confirmation is True
    assert [candidate.text for candidate in draft.candidates] == ["12 + 3"]

    empty = OcrResultDraft.from_parse_result(
        parse_paddle_text_result({"rec_texts": [], "rec_scores": []})
    )
    assert empty.status is OcrResultStatus.EMPTY
    assert empty.confidence == 0.0
    assert empty.candidates == ()

    with pytest.raises(ValidationError):
        OcrResultDraft(
            provider="local_paddleocr",
            model="PP-OCRv6_medium",
            model_version="v6",
            schema_version="ocr-result.v1",
            confidence=0.9,
            status=OcrResultStatus.EMPTY,
            candidates=({"text": "candidate\nwith-control", "confidence": 0.9},),
        )


def _headers(
    client: TestClient, role: str = "parent", child_id: UUID | None = None
) -> dict[str, str]:
    return session_headers(client, role=role, child_id=child_id)


def _past_date() -> date:
    return date(2020, 1, 1) + timedelta(days=uuid4().int % 2000)


def _capture(client: TestClient) -> UUID:
    task = client.post(
        f"/households/{HOUSEHOLD_A}/tasks",
        headers={**_headers(client), "Idempotency-Key": f"ocr-task-{uuid4()}"},
        json={
            "child_id": str(CHILD_A),
            "title": "OCR persistence task",
            "subject": "math",
            "scheduled_for": _past_date().isoformat(),
        },
    )
    assert task.status_code == 201
    session = client.post(
        f"/households/{HOUSEHOLD_A}/tasks/{task.json()['id']}/sessions",
        headers={**_headers(client, "child", CHILD_A), "Idempotency-Key": f"ocr-session-{uuid4()}"},
        json={"expected_task_version": 1},
    )
    assert session.status_code == 201
    capture = client.post(
        f"/households/{HOUSEHOLD_A}/sessions/{session.json()['id']}/captures",
        headers={**_headers(client, "child", CHILD_A), "Idempotency-Key": f"ocr-capture-{uuid4()}"},
        json={
            "media_type": "image/png",
            "byte_size": 2048,
            "content_sha256": "0" * 64,
        },
    )
    assert capture.status_code == 201
    return UUID(capture.json()["id"])


@pytest.mark.integration
def test_postgresql_ocr_result_is_normalized_manual_and_household_scoped() -> None:
    profiles = InMemoryProfileRepository()
    learning = PostgresLearningRepository(profiles)
    captures = PostgresCaptureRepository()
    results = PostgresOcrResultRepository()
    client = TestClient(create_app(profiles, learning, captures))
    try:
        capture_id = _capture(client)
        draft = OcrResultDraft.from_parse_result(
            parse_paddle_text_result({"rec_texts": ["12 + 3", "15"], "rec_scores": [0.96, 0.91]})
        )
        first, replayed = results.create_result(
            HOUSEHOLD_A, capture_id, CHILD_A, draft, "ocr-result-idempotency-001"
        )
        replay, was_replayed = results.create_result(
            HOUSEHOLD_A, capture_id, CHILD_A, draft, "ocr-result-idempotency-001"
        )
        loaded, candidates = results.get_result(HOUSEHOLD_A, first.id, CHILD_A)

        assert replayed is False
        assert was_replayed is True
        assert replay == first
        assert loaded == first
        assert first.requires_manual_confirmation is True
        assert [candidate.text for candidate in candidates] == ["12 + 3", "15"]
        assert all(candidate.result_id == first.id for candidate in candidates)

        with results.engine.connect() as connection:
            audits = (
                connection.execute(
                    select(results._audits).where(results._audits.c.resource_id == first.id)
                )
                .mappings()
                .all()
            )
        assert [audit["event_name"] for audit in audits] == ["ocr_result_created"]
        assert all("12 + 3" not in str(audit) for audit in audits)

        with pytest.raises(IdempotencyConflictError):
            results.create_result(
                HOUSEHOLD_A,
                capture_id,
                CHILD_A,
                draft.model_copy(update={"model_version": "different"}),
                "ocr-result-idempotency-001",
            )
        with pytest.raises(ChildAssignmentError):
            results.get_result(HOUSEHOLD_A, first.id, CHILD_B)
        with pytest.raises(LookupError):
            results.get_result(HOUSEHOLD_B, first.id, CHILD_B)
    finally:
        results.close()
        learning.close()
        captures.close()


@pytest.mark.integration
def test_postgresql_ocr_empty_result_is_persisted_without_candidates() -> None:
    profiles = InMemoryProfileRepository()
    learning = PostgresLearningRepository(profiles)
    captures = PostgresCaptureRepository()
    results = PostgresOcrResultRepository()
    client = TestClient(create_app(profiles, learning, captures))
    try:
        capture_id = _capture(client)
        draft = OcrResultDraft.from_parse_result(
            parse_paddle_text_result({"rec_texts": [], "rec_scores": []})
        )
        result, replayed = results.create_result(
            HOUSEHOLD_A, capture_id, CHILD_A, draft, "ocr-result-empty-001"
        )
        loaded, candidates = results.get_result(HOUSEHOLD_A, result.id, CHILD_A)

        assert replayed is False
        assert loaded.status is OcrResultStatus.EMPTY
        assert loaded.confidence == 0.0
        assert candidates == []
    finally:
        results.close()
        learning.close()
        captures.close()
