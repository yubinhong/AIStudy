"""Provider-neutral, offline Tutor Policy fallback.

This module intentionally does not call a model or inspect ``answer_text``.
It provides a deterministic, three-level prompt sequence for a confirmed
question so the child can continue learning while a Tutor Provider remains
unapproved. The response is a hint, never a verified answer.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from study_api.privacy_models import VerifiedQuestion


class TutorHintRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    verified_question: VerifiedQuestion
    level: int = Field(ge=1, le=3)


class StartTutorHintRequest(BaseModel):
    """Reference a server-owned verified fact; child identity comes from auth."""

    model_config = ConfigDict(frozen=True)

    verified_question_id: UUID
    level: int = Field(ge=1, le=3)


class TutorHintContent(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal["tutor-hint.v1"] = "tutor-hint.v1"
    policy_version: Literal["offline-tutor-policy.v1"] = "offline-tutor-policy.v1"
    provider: Literal["local-policy"] = "local-policy"
    model: Literal["rules-v1"] = "rules-v1"
    level: int = Field(ge=1, le=3)
    prompt: str = Field(min_length=1, max_length=500)
    next_step: str = Field(min_length=1, max_length=500)
    requires_child_response: Literal[True] = True
    direct_answer: None = None
    cost_cents: Literal[0] = 0


class TutorHintResponse(TutorHintContent):
    """Persisted Tutor turn returned to the authenticated child."""

    id: UUID
    verified_question_id: UUID
    created_at: datetime


_LEVEL_PROMPTS = {
    1: (
        "先用自己的话说一说：题目已经告诉了我们什么？最后要找什么？",
        "圈出已知的数和问题中的关键词，再说给自己听。",
    ),
    2: (
        "把题目变成一个小步骤：第一步应该比较、合并，还是拆分这些数量？为什么？",
        "只写出第一步的算式，不急着算完，然后检查它是否回答了题目。",
    ),
    3: (
        "现在试着完成你的算式，并解释每一步为什么这样做。你能用另一种方法检查吗？",
        "完成后回看单位、分母或数量关系，确认答案和问题问的内容一致。",
    ),
}


def create_offline_hint(request: TutorHintRequest) -> TutorHintContent:
    """Return the next bounded hint for a human-confirmed math question."""

    prompt, next_step = _LEVEL_PROMPTS[request.level]
    # Reading only structural fields keeps the future routing seam explicit:
    # no answer, candidate text, or Provider payload is copied to the output.
    if request.verified_question.formulas:
        next_step = f"{next_step} 题目里有公式时，先确认每个符号代表什么。"
    return TutorHintContent(level=request.level, prompt=prompt, next_step=next_step)
