from datetime import UTC, datetime
from uuid import uuid4

from study_api.privacy_models import VerifiedQuestion
from study_api.tutor_policy import TutorHintRequest, create_offline_hint


def _question(*, answer: str | None = "5/8") -> VerifiedQuestion:
    return VerifiedQuestion(
        id=uuid4(),
        capture_id=uuid4(),
        extraction_id=uuid4(),
        version=1,
        subject="math",
        question_text="3/4 + 1/8 = ?",
        options=(),
        formulas=("3/4 + 1/8",),
        has_diagram=False,
        has_handwriting=False,
        answer_text=answer,
        verified_by="child",
        verified_at=datetime.now(UTC),
    )


def test_offline_policy_returns_three_bounded_hint_levels_without_answer() -> None:
    for level in (1, 2, 3):
        response = create_offline_hint(TutorHintRequest(verified_question=_question(), level=level))
        assert response.level == level
        assert response.requires_child_response is True
        assert response.direct_answer is None
        assert "5/8" not in response.prompt + response.next_step
        assert response.cost_cents == 0


def test_offline_policy_does_not_copy_verified_answer_even_when_present() -> None:
    response = create_offline_hint(
        TutorHintRequest(verified_question=_question(answer="7/9"), level=2)
    )
    assert "7/9" not in response.model_dump_json()
