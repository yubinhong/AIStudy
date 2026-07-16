from uuid import uuid4

import pytest

from study_api.domain.repository import IdempotencyConflictError
from study_api.domain.verified_question_repository import InMemoryVerifiedQuestionRepository
from study_api.privacy_models import VerifyQuestionRequest


def _request() -> VerifyQuestionRequest:
    return VerifyQuestionRequest(
        expected_capture_version=2,
        question_text="3/4 + 1/8 = ?",
        formulas=("3/4 + 1/8",),
        has_diagram=False,
        has_handwriting=False,
    )


def test_verified_question_is_idempotent_and_keeps_extraction_immutable() -> None:
    repository = InMemoryVerifiedQuestionRepository()
    household_id, child_id, capture_id, extraction_id = (uuid4() for _ in range(4))

    first, replayed = repository.create(
        household_id,
        child_id,
        capture_id,
        extraction_id,
        _request(),
        "child",
        "verify-question-001",
    )
    replay, was_replayed = repository.create(
        household_id,
        child_id,
        capture_id,
        extraction_id,
        _request(),
        "child",
        "verify-question-001",
    )

    assert replayed is False
    assert was_replayed is True
    assert replay == first
    assert repository.get(household_id, child_id, capture_id, extraction_id) == first

    with pytest.raises(IdempotencyConflictError):
        repository.create(
            household_id,
            child_id,
            capture_id,
            extraction_id,
            _request().model_copy(update={"question_text": "different"}),
            "child",
            "verify-question-001",
        )


def test_verified_question_cannot_cross_child_scope() -> None:
    repository = InMemoryVerifiedQuestionRepository()
    household_id, child_id, capture_id, extraction_id = (uuid4() for _ in range(4))
    repository.create(
        household_id,
        child_id,
        capture_id,
        extraction_id,
        _request(),
        "parent",
        "verify-question-002",
    )

    with pytest.raises(LookupError):
        repository.get(household_id, uuid4(), capture_id, extraction_id)
