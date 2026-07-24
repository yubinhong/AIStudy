"""Run the deterministic offline Tutor Policy synthetic gate."""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from study_api.domain.models import AnswerState
from study_api.privacy_models import VerifiedQuestion
from study_api.tutor_policy import TutorHintRequest, TutorMode, create_offline_hint


def main() -> int:
    fixture = json.loads(
        (Path(__file__).parent / "fixtures/tutor_policy_synthetic_v1.json").read_text()
    )
    question = VerifiedQuestion(
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
        answer_text="7/8",
        verified_by="child",
        verified_at=datetime.now(UTC),
    )
    passed = 0
    for case in fixture["cases"]:
        response = create_offline_hint(
            TutorHintRequest(verified_question=question, level=case["level"])
        )
        serialized = response.model_dump_json()
        if response.direct_answer is not None or "7/8" in serialized:
            raise SystemExit(f"failed: {case['id']}")
        passed += 1
    duration_question = question.model_copy(
        update={
            "question_text": "三名同学同时阅读了20分钟，每名同学阅读了多长时间？",
            "formulas": (),
            "answer_text": None,
        }
    )
    for level, expected in ((1, "同时"), (2, "时间线")):
        response = create_offline_hint(
            TutorHintRequest(
                verified_question=duration_question,
                level=level,
                mode=TutorMode.MISTAKE_EXPLANATION,
                answer_state=AnswerState.BLANK,
            )
        )
        serialized = response.model_dump_json()
        if (
            expected not in serialized
            or "平均分" in serialized
            or "20分钟" in response.next_step
        ):
            raise SystemExit(f"failed: simultaneous-duration-l{level}")
        passed += 1
    print(
        json.dumps(
            {
                "eval": fixture["schema_version"],
                "cases": passed,
                "provider_calls": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
