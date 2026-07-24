"""Provider-neutral, offline Tutor Policy fallback.

This module intentionally does not call a model or inspect ``answer_text``.
It provides a deterministic, three-level prompt sequence for a confirmed
question so the child can continue learning while a Tutor Provider remains
unapproved. The response is a hint, never a verified answer.
"""

import re
from datetime import datetime
from difflib import SequenceMatcher
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from study_api.domain.models import AnswerState
from study_api.privacy_models import VerifiedQuestion

SolutionStep = Annotated[str, Field(min_length=1, max_length=1000)]


class TutorMode(str):
    GUIDED_PRACTICE = "guided_practice"
    REVIEW = "review"
    MISTAKE_EXPLANATION = "mistake_explanation"


class TutorHintRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    verified_question: VerifiedQuestion
    level: int = Field(ge=1, le=3)
    mode: str = Field(
        default=TutorMode.GUIDED_PRACTICE,
        pattern=r"^(guided_practice|review|mistake_explanation)$",
    )
    answer_state: AnswerState | None = None


class StartTutorHintRequest(BaseModel):
    """Reference a server-owned verified fact; child identity comes from auth."""

    model_config = ConfigDict(frozen=True)

    verified_question_id: UUID
    level: int = Field(ge=1, le=3)
    mode: str = Field(
        default=TutorMode.GUIDED_PRACTICE,
        pattern=r"^(guided_practice|review|mistake_explanation)$",
    )
    answer_state: AnswerState | None = None
    evidence_confirmed: bool = False


class CurriculumSource(BaseModel):
    model_config = ConfigDict(frozen=True)

    snapshot_id: UUID
    page_number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=160)
    confidence: float = Field(ge=0, le=1)


class TutorHintContent(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal["tutor-hint.v1"] = "tutor-hint.v1"
    policy_version: str = Field(default="offline-tutor-policy.v3", min_length=1, max_length=80)
    provider: str = Field(default="local-policy", min_length=1, max_length=80)
    model: str = Field(default="rules-v2", min_length=1, max_length=120)
    level: int = Field(ge=1, le=3)
    mode: str = Field(
        default=TutorMode.GUIDED_PRACTICE,
        pattern=r"^(guided_practice|review|mistake_explanation)$",
    )
    answer_state: AnswerState | None = None
    prompt: str = Field(min_length=1, max_length=500)
    next_step: str = Field(min_length=1, max_length=500)
    requires_child_response: bool = True
    direct_answer: str | None = Field(default=None, max_length=1000)
    solution_steps: tuple[SolutionStep, ...] = Field(default=(), max_length=12)
    verification: str | None = Field(default=None, max_length=1000)
    cost_cents: int = Field(default=0, ge=0)
    curriculum_sources: tuple[CurriculumSource, ...] = Field(default=(), max_length=5)
    hint_goal: str = Field(default="understand_the_question", min_length=1, max_length=80)
    builds_on_turn_id: UUID | None = None
    revealed_elements: tuple[str, ...] = Field(default=(), max_length=8)
    child_action: str = Field(default="用自己的话说出下一步。", min_length=1, max_length=300)
    answer_exposure: Literal["none", "partial", "full"] = "none"


class DetailedSolution(BaseModel):
    """Provider-neutral, validated solution for a confirmed question."""

    model_config = ConfigDict(frozen=True)

    steps: tuple[SolutionStep, ...] = Field(min_length=1, max_length=12)
    final_answer: str = Field(min_length=1, max_length=1000)
    verification: str = Field(min_length=1, max_length=1000)


class GeneratedTutorHint(BaseModel):
    """Strict text-only Provider result for L1/L2."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    prompt: str = Field(min_length=1, max_length=500)
    next_step: str = Field(min_length=1, max_length=500)
    child_action: str = Field(min_length=1, max_length=300)
    revealed_elements: tuple[
        Literal[
            "known_and_unknown",
            "key_relationship",
            "error_location",
            "method_choice",
            "representation_scaffold",
            "first_step_scaffold",
        ],
        ...,
    ] = Field(min_length=1, max_length=6)


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


def _question_specific_prompt(question: VerifiedQuestion, level: int) -> tuple[str, str] | None:
    """Return a bounded, answer-free prompt for common primary math wording."""

    text = question.question_text
    removal_words = ("飞走", "离开", "用掉", "吃掉", "卖出", "拿走", "借出")
    remainder_words = ("还剩", "剩下", "现在", "还有多少")
    comparison_words = ("多多少", "少多少", "相差", "差多少")
    grouping_words = ("平均", "每份", "每组", "分成", "可以分")
    total_words = ("一共", "总共", "合计", "共有多少")
    simultaneous_words = ("一起", "同时", "共同", "同一时间", "同步")
    duration_words = ("分钟", "小时", "时长", "时间")

    if any(word in text for word in simultaneous_words) and any(
        word in text for word in duration_words
    ):
        prompts = {
            1: (
                "先抓住“同时”这个条件：这些人是一起经历同一段时间，还是一个接一个轮流进行？",
                "在题目中圈出表示同时开始、同时结束的词，再说说人数会不会改变钟表经过的时间。",
            ),
            2: (
                "可以画一条从开始到结束的时间线，把每个人的起点和终点上下对齐；这里先不要按人数去乘或除时间。",
                "画出同一段时间线并标出每个人都覆盖哪一段，再根据图说出你的判断。",
            ),
            3: (
                "按“所有人同时开始、同时结束”的关系完成解答，不要把共同经历的时长当成需要平均分的总量。",
                "写出结论后，用开始和结束时刻相同来检查。",
            ),
        }
        return prompts[level]

    if any(word in text for word in removal_words) and any(
        word in text for word in remainder_words
    ):
        prompts = {
            1: (
                "题目里有原来的数量和减少的数量。先想一想：每次飞走或用掉，数量是在增加还是减少？",
                "先圈出原来的数量、每次减少的数量和最后要求的数量。",
            ),
            2: (
                "如果题目发生了两次减少，可以先求两次一共减少了多少，再想怎样得到现在的数量。",
                "先写求“总共减少多少”的第一步算式，暂时不要写最终答案。",
            ),
            3: (
                "检查你的思路：第一步有没有合并所有减少量，下一步是不是从原来的数量中去掉它？",
                "按发生顺序写出算式，再用题目中的“现在”检查结果表示的含义。",
            ),
        }
        return prompts[level]
    if any(word in text for word in comparison_words):
        return (
            "这道题在比较两个数量。先找出谁多、谁少，再想“相差”要用什么关系表示。",
            "把两个要比较的数量放在一起，只写出求差的第一步。",
        )
    if any(word in text for word in grouping_words):
        return (
            "题目在把一个总量平均分组。先分清总量、每组数量和组数中哪两个是已知的。",
            "画几个同样大小的小组，再把已知数量放进去。",
        )
    if any(word in text for word in total_words):
        return (
            "题目要找合起来的总量。先找出需要合并的是哪几个部分。",
            "只写出把这些部分合并的第一步算式。",
        )
    if question.formulas and ("/" in text or "分母" in text or "分数" in text):
        return _LEVEL_PROMPTS[level]
    return None


def create_offline_hint(request: TutorHintRequest) -> TutorHintContent:
    """Return the next bounded hint for a human-confirmed math question."""

    specific_prompt = _question_specific_prompt(request.verified_question, request.level)
    prompt, next_step = specific_prompt or _LEVEL_PROMPTS[request.level]
    if request.answer_state is AnswerState.ANSWER_AREA_MISSING:
        prompt = "这张照片没有拍到作答区域，需要先确认作答状态，暂时不能判断你已经做到哪一步。"
        next_step = "请重新拍摄包含题目和完整答题区的照片，再继续针对性讲解。"
    elif request.answer_state is AnswerState.UNCLEAR:
        prompt = "作答痕迹目前看不清，需要先确认作答状态，暂时不能把它判断成空白或已有作答。"
        next_step = "请先确认作答状态；如果字迹较浅，可以重新拍一张更清晰的照片。"
    elif request.mode == TutorMode.MISTAKE_EXPLANATION:
        if request.answer_state is AnswerState.WORKED:
            if request.level == 1:
                prompt = "先找出你已经写出的第一步：哪一个等号或数量关系最值得重新检查？"
                next_step = "只检查一个步骤，说明它为什么成立或哪里需要改正。"
            elif request.level == 2:
                prompt = "把你的每一步依次和题目条件对照：最早从哪一步开始没有使用正确的数量关系？"
                next_step = "先改正最早的一处：写出题目条件对应的正确数量关系，再重算后续一步。"
            else:
                prompt = "现在按修正后的数量关系完整重做，并在每一步写出依据。"
                next_step = "完成后用另一种表示或验算检查结果，确认它回答了题目。"
        elif request.answer_state is AnswerState.BLANK:
            if request.level == 1:
                if specific_prompt is None:
                    prompt = "先不用急着算：题目中的已知和所求分别是什么？"
                    next_step = "把已知量和问题各写成一句话，再选择第一步。"
            elif request.level == 2:
                if specific_prompt is None:
                    prompt = "根据已知和所求，先判断数量是在增加、减少、比较还是平均分。"
                    next_step = "只列出第一步算式，并说清这个算式先求出了什么。"
            else:
                prompt = "沿着第一步继续完成解法，并把每一个数量关系和题目条件对应起来。"
                next_step = "写完后检查单位、数量方向和最终问题是否一致。"
    elif request.mode == TutorMode.REVIEW:
        prompt = "先回忆上次卡住的地方：这道题最容易漏掉哪一个关系？"
        next_step = "不看答案，先写出一个检查步骤，再和题目条件对照。"
    # Reading only structural fields keeps the future routing seam explicit:
    # no answer, candidate text, or Provider payload is copied to the output.
    if request.verified_question.formulas:
        next_step = f"{next_step} 题目里有公式时，先确认每个符号代表什么。"
    revealed_elements: tuple[str, ...]
    if request.level == 1:
        hint_goal = "understand_the_question"
        revealed_elements = ("known_and_unknown",)
        child_action = "指出一个已知条件和题目要找的内容。"
    elif request.level == 2:
        hint_goal = "choose_a_method"
        revealed_elements = ("method_choice", "first_step_scaffold")
        child_action = "写出第一步，并说清它先求出了什么。"
    else:
        hint_goal = "complete_and_check"
        revealed_elements = ("solution_steps", "final_answer", "verification")
        child_action = "完成解答后，用题目条件再检查一次。"
    return TutorHintContent(
        level=request.level,
        prompt=prompt,
        next_step=next_step,
        mode=request.mode,
        answer_state=request.answer_state,
        hint_goal=hint_goal,
        revealed_elements=revealed_elements,
        child_action=child_action,
        answer_exposure="full" if request.level == 3 else "none",
    )


_ANSWER_MARKERS = ("答案是", "答案为", "所以答案", "最终答案", "结果是", "结果为")
_SOLVED_EQUATION = re.compile(r"=\s*-?\d+(?:\.\d+)?(?:\s*[个只本米厘米分钟小时元角分])?")
_SIMULTANEOUS_ANSWER = re.compile(
    r"(?:每人|每个人|他们每一个人).{0,8}(?:玩|经历|用了?).{0,5}\d+\s*(?:分钟|小时)"
)


def validate_generated_hint(
    generated: GeneratedTutorHint,
    *,
    level: int,
    previous: TutorHintResponse | None,
    question_text: str,
) -> None:
    """Reject answer leakage, repetition and non-progressive Provider hints."""

    combined = f"{generated.prompt}\n{generated.next_step}\n{generated.child_action}"
    if any(marker in combined for marker in _ANSWER_MARKERS):
        raise ValueError("generated hint exposes a direct conclusion")
    if _SOLVED_EQUATION.search(combined) or _SIMULTANEOUS_ANSWER.search(combined):
        raise ValueError("generated hint exposes a solved answer")
    normalized_question = "".join(question_text.split())
    if any(word in normalized_question for word in ("同时", "一起", "同一时间")) and any(
        word in normalized_question for word in ("分钟", "小时", "时间")
    ):
        if not any(
            word in combined for word in ("同时", "一起", "同一段时间", "开始", "结束", "时间线")
        ):
            raise ValueError("generated hint ignores the simultaneous-time relationship")
    if any(
        word in normalized_question for word in ("分数", "分母", "分子", "几分之", "/")
    ) and not any(word in combined for word in ("分数", "分母", "分子", "通分", "同样大小的份")):
        raise ValueError("generated hint ignores the fraction relationship")
    revealed = set(generated.revealed_elements)
    if level == 1:
        if "key_relationship" not in revealed:
            raise ValueError("L1 must identify the question-specific relationship")
        if revealed.intersection(
            {"method_choice", "representation_scaffold", "first_step_scaffold"}
        ):
            raise ValueError("L1 must not reveal the method scaffold")
        return
    if level != 2 or previous is None:
        raise ValueError("L2 requires a persisted L1 turn")
    scaffold = {"method_choice", "representation_scaffold", "first_step_scaffold"}
    if not revealed.intersection(scaffold):
        raise ValueError("L2 must add a method scaffold")
    if not revealed.difference(previous.revealed_elements):
        raise ValueError("L2 must reveal more than L1")
    previous_text = f"{previous.prompt}\n{previous.next_step}\n{previous.child_action}"
    if SequenceMatcher(None, previous_text, combined).ratio() >= 0.82:
        raise ValueError("L2 merely repeats L1")
