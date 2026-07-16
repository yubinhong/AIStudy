from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from study_api.domain.learning_repository import ChildAssignmentError
from study_api.domain.models import (
    CaptureCorrection,
    CorrectCaptureRequest,
    OcrCandidate,
    OcrResult,
    OcrResultStatus,
)
from study_api.domain.ocr_result_repository import (
    InMemoryOcrResultRepository,
    OcrCandidateDraft,
    OcrResultDraft,
)
from study_api.main import create_app

HOUSEHOLD_A = UUID("00000000-0000-0000-0000-000000000001")
HOUSEHOLD_B = UUID("00000000-0000-0000-0000-000000000002")
CHILD_A = UUID("00000000-0000-0000-0000-000000000101")
CHILD_B = UUID("00000000-0000-0000-0000-000000000102")
CAPTURE_ID = UUID("00000000-0000-0000-0000-000000000201")


def _headers(
    household_id: UUID = HOUSEHOLD_A,
    role: str = "child",
    child_id: UUID | None = CHILD_A,
) -> dict[str, str]:
    headers = {
        "X-Demo-Household-Id": str(household_id),
        "X-Demo-Role": role,
    }
    if child_id is not None:
        headers["X-Demo-Child-Id"] = str(child_id)
    return headers


def _result(capture_id: UUID = CAPTURE_ID) -> tuple[OcrResult, list[OcrCandidate]]:
    result_id = uuid4()
    result = OcrResult(
        id=result_id,
        capture_id=capture_id,
        household_id=HOUSEHOLD_A,
        child_id=CHILD_A,
        provider="local_paddleocr",
        model="PP-OCRv6_medium",
        model_version="synthetic",
        schema_version="ocr-result.v1",
        confidence=0.91,
        status=OcrResultStatus.CANDIDATE,
        requires_manual_confirmation=True,
        created_at=datetime.now(UTC),
    )
    return result, [
        OcrCandidate(
            id=uuid4(),
            result_id=result_id,
            sequence=1,
            text="synthetic 3 + 4",
            confidence=0.91,
        )
    ]


class FakeOcrResults:
    def __init__(self) -> None:
        self.result, self.candidates = _result()

    def get_result(
        self, household_id: UUID, result_id: UUID, child_id: UUID
    ) -> tuple[OcrResult, list[OcrCandidate]]:
        if household_id != self.result.household_id or result_id != self.result.id:
            raise LookupError
        if child_id != self.result.child_id:
            raise ChildAssignmentError
        return self.result, self.candidates


class FakeCaptures:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, UUID, UUID, str]] = []
        self.operation_prefixes: list[str] = []
        self.correction = CaptureCorrection(
            id=uuid4(),
            capture_id=CAPTURE_ID,
            household_id=HOUSEHOLD_A,
            child_id=CHILD_A,
            sequence=1,
            corrected_text="synthetic 3 + 4",
            created_at=datetime.now(UTC),
        )

    def correct_capture(
        self,
        household_id: UUID,
        capture_id: UUID,
        child_id: UUID,
        request: CorrectCaptureRequest,
        idempotency_key: str,
        *,
        operation_prefix: str = "correct_capture",
    ) -> tuple[CaptureCorrection, bool]:
        self.calls.append((household_id, capture_id, child_id, idempotency_key))
        self.operation_prefixes.append(operation_prefix)
        return self.correction, len(self.calls) > 1


def test_child_can_read_unverified_candidates_for_the_matching_capture() -> None:
    results = FakeOcrResults()
    client = TestClient(create_app(ocr_result_repository=results))

    response = client.get(
        f"/households/{HOUSEHOLD_A}/captures/{CAPTURE_ID}/ocr-results/{results.result.id}",
        headers=_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["requires_manual_confirmation"] is True
    assert body["candidates"][0]["text"] == "synthetic 3 + 4"


def test_ocr_result_read_rejects_sibling_parent_and_other_household() -> None:
    results = FakeOcrResults()
    client = TestClient(create_app(ocr_result_repository=results))
    path = f"/households/{HOUSEHOLD_A}/captures/{CAPTURE_ID}/ocr-results/{results.result.id}"

    sibling = client.get(path, headers=_headers(child_id=CHILD_B))
    parent = client.get(path, headers=_headers(role="parent", child_id=None))
    other_household = client.get(
        f"/households/{HOUSEHOLD_B}/captures/{CAPTURE_ID}/ocr-results/{results.result.id}",
        headers=_headers(HOUSEHOLD_B, child_id=CHILD_B),
    )

    assert sibling.status_code == 404
    assert parent.status_code == 403
    assert other_household.status_code == 404


def test_ocr_result_read_rejects_capture_id_mismatch() -> None:
    results = FakeOcrResults()
    client = TestClient(create_app(ocr_result_repository=results))

    response = client.get(
        f"/households/{HOUSEHOLD_A}/captures/{uuid4()}/ocr-results/{results.result.id}",
        headers=_headers(),
    )

    assert response.status_code == 404


def test_inmemory_ocr_result_repository_is_idempotent_and_child_bound() -> None:
    repository = InMemoryOcrResultRepository()
    draft = OcrResultDraft(
        provider="local_paddleocr",
        model="PP-OCRv6_medium",
        model_version="synthetic",
        schema_version="ocr-result.v1",
        confidence=0.9,
        status=OcrResultStatus.CANDIDATE,
        candidates=(OcrCandidateDraft(text="synthetic 8", confidence=0.9),),
    )
    result, replayed = repository.create_result(
        HOUSEHOLD_A, CAPTURE_ID, CHILD_A, draft, "ocr-result-route-001"
    )
    replay, replayed_again = repository.create_result(
        HOUSEHOLD_A, CAPTURE_ID, CHILD_A, draft, "ocr-result-route-001"
    )

    assert replayed is False
    assert replayed_again is True
    assert replay.id == result.id
    assert repository.get_result(HOUSEHOLD_A, result.id, CHILD_A)[0].id == result.id


def test_child_can_confirm_a_selected_candidate_as_an_append_only_correction() -> None:
    results = FakeOcrResults()
    captures = FakeCaptures()
    client = TestClient(create_app(capture_repository=captures, ocr_result_repository=results))
    path = (
        f"/households/{HOUSEHOLD_A}/captures/{CAPTURE_ID}/ocr-results/"
        f"{results.result.id}/confirmations"
    )
    payload = {
        "expected_capture_version": 1,
        "candidate_id": str(results.candidates[0].id),
    }
    headers = {**_headers(), "Idempotency-Key": "ocr-confirm-route-001"}

    first = client.post(path, headers=headers, json=payload)
    replay = client.post(path, headers=headers, json=payload)
    read_back = client.get(path.removesuffix("/confirmations"), headers=_headers())

    assert first.status_code == 201
    assert first.json()["corrected_text"] == "synthetic 3 + 4"
    assert replay.status_code == 200
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert len(captures.calls) == 2
    assert captures.calls[0][3] == "ocr-confirm-route-001"
    assert captures.operation_prefixes[0] == f"confirm_ocr_candidate:{results.result.id}"
    assert read_back.status_code == 200
    assert read_back.json()["result"]["requires_manual_confirmation"] is True


def test_ocr_candidate_confirmation_rejects_unknown_candidate_and_parent() -> None:
    results = FakeOcrResults()
    captures = FakeCaptures()
    client = TestClient(create_app(capture_repository=captures, ocr_result_repository=results))
    path = (
        f"/households/{HOUSEHOLD_A}/captures/{CAPTURE_ID}/ocr-results/"
        f"{results.result.id}/confirmations"
    )
    unknown = client.post(
        path,
        headers={**_headers(), "Idempotency-Key": "ocr-confirm-unknown"},
        json={"expected_capture_version": 1, "candidate_id": str(uuid4())},
    )
    parent = client.post(
        path,
        headers={**_headers(role="parent", child_id=None), "Idempotency-Key": "ocr-confirm-parent"},
        json={
            "expected_capture_version": 1,
            "candidate_id": str(results.candidates[0].id),
        },
    )

    assert unknown.status_code == 404
    assert parent.status_code == 403
    assert captures.calls == []
