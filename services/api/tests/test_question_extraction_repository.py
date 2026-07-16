from uuid import uuid4

from study_api.domain.question_extraction_repository import (
    InMemoryQuestionExtractionRepository,
)
from study_api.privacy_models import QuestionExtraction


def test_extraction_repository_is_idempotent_and_scoped() -> None:
    repository = InMemoryQuestionExtractionRepository()
    job_id, household_id, capture_id, child_id = uuid4(), uuid4(), uuid4(), uuid4()
    extraction = QuestionExtraction(
        subject="math",
        question_text="3/4 + 1/8 = ?",
        options=(),
        formulas=("3/4 + 1/8",),
        has_diagram=False,
        has_handwriting=False,
        question_region_count=1,
        confidence=0.92,
    )

    first, replayed = repository.create(job_id, household_id, capture_id, child_id, extraction)
    second, replayed_again = repository.create(
        job_id, household_id, capture_id, child_id, extraction
    )

    assert replayed is False
    assert replayed_again is True
    assert second == first
    assert repository.get(household_id, capture_id, first.id, child_id) == first
