from datetime import UTC, datetime
from uuid import uuid4

import pytest

from study_api.domain.models import AnswerState
from study_api.privacy_models import VerifiedQuestion
from study_api.tutor_policy import (
    GeneratedTutorHint,
    TutorHintRequest,
    TutorMode,
    create_offline_hint,
    validate_generated_hint,
)


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


def test_offline_policy_uses_the_confirmed_word_problem_structure() -> None:
    question = _question(answer="17")
    question = question.model_copy(
        update={
            "question_text": (
                "花丛中有蜻蜓和蝴蝶共35只，飞走了6只，又飞走了12只。现在花丛中蜻蜓和蝴蝶有多少只？"
            ),
            "formulas": (),
        }
    )

    first = create_offline_hint(TutorHintRequest(verified_question=question, level=1))
    second = create_offline_hint(TutorHintRequest(verified_question=question, level=2))

    assert "减少" in first.prompt
    assert "两次" in second.prompt
    assert "17" not in first.model_dump_json() + second.model_dump_json()


def test_mistake_explanation_branches_on_the_four_answer_states() -> None:
    worked = create_offline_hint(
        TutorHintRequest(
            verified_question=_question(),
            level=1,
            mode=TutorMode.MISTAKE_EXPLANATION,
            answer_state=AnswerState.WORKED,
        )
    )
    blank = create_offline_hint(
        TutorHintRequest(
            verified_question=_question(),
            level=1,
            mode=TutorMode.MISTAKE_EXPLANATION,
            answer_state=AnswerState.BLANK,
        )
    )
    unclear = create_offline_hint(
        TutorHintRequest(
            verified_question=_question(),
            level=1,
            mode=TutorMode.MISTAKE_EXPLANATION,
            answer_state=AnswerState.UNCLEAR,
        )
    )
    missing = create_offline_hint(
        TutorHintRequest(
            verified_question=_question(),
            level=1,
            mode=TutorMode.MISTAKE_EXPLANATION,
            answer_state=AnswerState.ANSWER_AREA_MISSING,
        )
    )
    assert worked.prompt != blank.prompt
    assert "确认作答状态" in unclear.prompt
    assert "确认作答状态" in missing.prompt


def test_simultaneous_duration_hints_do_not_treat_time_as_average_sharing() -> None:
    question = _question(answer=None).model_copy(
        update={
            "question_text": ("四个青年人一起玩扑克，玩了40分钟。他们每一个人玩了多长时间？"),
            "formulas": (),
        }
    )
    first = create_offline_hint(
        TutorHintRequest(
            verified_question=question,
            level=1,
            mode=TutorMode.MISTAKE_EXPLANATION,
            answer_state=AnswerState.BLANK,
        )
    )
    second = create_offline_hint(
        TutorHintRequest(
            verified_question=question,
            level=2,
            mode=TutorMode.MISTAKE_EXPLANATION,
            answer_state=AnswerState.BLANK,
        )
    )

    assert "同时" in first.prompt
    assert "时间线" in second.prompt
    assert "平均分" not in first.model_dump_json() + second.model_dump_json()
    assert "每一个人玩了40分钟" not in first.model_dump_json() + second.model_dump_json()


def test_cloud_hint_is_rejected_when_it_ignores_the_question_relationship() -> None:
    generic = GeneratedTutorHint(
        prompt="根据已知和所求，先判断数量是在增加、减少、比较还是平均分。",
        next_step="只列出第一步算式，并说清这个算式先求出了什么。",
        child_action="写出第一步。",
        revealed_elements=("known_and_unknown", "key_relationship"),
    )

    with pytest.raises(ValueError, match="simultaneous-time"):
        validate_generated_hint(
            generic,
            level=1,
            previous=None,
            question_text="四个人一起玩了40分钟，每个人玩了多长时间？",
        )
