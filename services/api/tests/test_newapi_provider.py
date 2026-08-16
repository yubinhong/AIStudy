import base64
import io
import json
import logging
from collections.abc import Mapping
from typing import Any
from uuid import UUID

import pytest
from PIL import Image

from study_api.domain.models import Subject
from study_api.newapi_provider import (
    CurriculumProviderPage,
    NewApiConfig,
    NewApiConfigurationError,
    NewApiProviderError,
    NewApiVisionProvider,
    _validated_curriculum_book,
)
from study_api.recommendation_engine import RecommendationSource


def _config() -> NewApiConfig:
    return NewApiConfig(True, "http://newapi.local", "key", "vision-model", 5, 100_000)


def test_newapi_provider_validates_structured_question_without_network() -> None:
    provider = NewApiVisionProvider(_config())
    captured: dict[str, Any] = {}

    def fake_post(payload: dict[str, Any]) -> dict[str, Any]:
        captured.update(payload)
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"subject":"math","question_text":"1 + 1 = ?",'
                            '"options":[],"formulas":[],"has_diagram":false,'
                            '"has_handwriting":false,"answer_state":"blank",'
                            '"answer_state_confidence":0.94,"answer_steps":[],'
                            '"question_region_count":1,'
                            '"confidence":0.9,"needs_confirmation":true}'
                        )
                    }
                }
            ]
        }

    provider._post_json = fake_post  # type: ignore[method-assign]
    result = provider.analyze_sanitized_image(
        b"synthetic", "image/png", sanitization_schema="privacy-sanitization.v1"
    )
    assert result.subject == "math"
    assert result.answer_state.value == "blank"
    assert result.needs_confirmation is True
    system_prompt = captured["messages"][0]["content"]
    for field in (
        "schema_version",
        "question_text",
        "options",
        "formulas",
        "has_diagram",
        "has_handwriting",
        "answer_state",
        "answer_state_confidence",
        "answer_steps",
        "question_region_count",
        "confidence",
        "needs_confirmation",
    ):
        assert field in system_prompt
    assert "Never solve the question" in system_prompt


def test_newapi_provider_rejects_invalid_response_and_unsafe_config() -> None:
    with pytest.raises(NewApiConfigurationError):
        NewApiVisionProvider(NewApiConfig(True, "", "", "", 0, 1))
    provider = NewApiVisionProvider(_config())
    provider._post_json = lambda _: {"choices": []}  # type: ignore[method-assign]
    with pytest.raises(NewApiProviderError):
        provider.analyze_sanitized_image(b"synthetic", "image/png", sanitization_schema="v1")


def test_newapi_provider_returns_only_bounded_picture_writing_scaffolds() -> None:
    provider = NewApiVisionProvider(_config())
    captured: dict[str, Any] = {}

    def fake_post(payload: dict[str, Any]) -> dict[str, Any]:
        captured.update(payload)
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "schema_version": "picture-writing-guide.v1",
                                "scene_observations": ["画面里有一棵树。", "一个孩子在浇花。"],
                                "focus_questions": ["谁在做什么？", "周围还有什么？"],
                                "sentence_starters": ["图上有", "我看见"],
                                "detail_prompts": ["说说动作。", "再看看地点。"],
                                "confidence": 0.9,
                                "needs_confirmation": True,
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    provider._post_json = fake_post  # type: ignore[method-assign]
    guide = provider.create_picture_writing_guide(
        b"synthetic", "image/png", sanitization_schema="privacy-sanitization.v1"
    )

    assert guide.schema_version == "picture-writing-guide.v1"
    assert guide.scene_observations == ("画面里有一棵树。", "一个孩子在浇花。")
    prompt = captured["messages"][0]["content"]
    assert "Never write a complete composition" in prompt
    assert "question-extraction.v1" not in prompt


def test_newapi_provider_bounds_whole_book_observation_payload() -> None:
    provider = NewApiVisionProvider(_config())

    with pytest.raises(NewApiProviderError, match="bounded input") as error:
        provider.consolidate_curriculum_book(page_observations=({"summary": "x" * 2_000_001},))

    assert error.value.code == "provider_curriculum_book_input_too_large"


def test_curriculum_book_discards_incomplete_points_and_invalid_optional_references() -> None:
    response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "schema_version": "curriculum-book-analysis.v1",
                            "book_summary": "一年级数学教材的知识结构。",
                            "chapters": [
                                {
                                    "title": "封面与目录",
                                    "start_page": 1,
                                    "end_page": 2,
                                    "summary": "不包含可审核的知识点。",
                                    "knowledge_points": None,
                                },
                                {
                                    "title": "第一单元",
                                    "start_page": 3,
                                    "end_page": 4,
                                    "summary": "认识数字。",
                                    "knowledge_points": [
                                        {
                                            "knowledge_key": "kp-counting",
                                            "section_title": "数一数",
                                            "title": "认识 1 到 5",
                                            "summary": "根据实物数量认读数字。",
                                            "learning_objectives": [],
                                            "prerequisites": None,
                                            "page_numbers": [3],
                                            "exercise_keys": None,
                                            "confidence": 0.9,
                                        },
                                        {
                                            "knowledge_key": "kp-counting-complete",
                                            "section_title": "数一数",
                                            "title": "按数量分类",
                                            "summary": "根据实物数量进行分类。",
                                            "learning_objectives": ["能按数量分类"] * 11,
                                            "prerequisites": ["已认识数量"] * 11,
                                            "page_numbers": [4],
                                            "exercise_keys": [
                                                f"page:4:observation:0:exercise:{index}"
                                                for index in range(31)
                                            ],
                                            "confidence": 0.9,
                                        },
                                    ],
                                },
                            ],
                        },
                        ensure_ascii=False,
                    )
                }
            }
        ]
    }

    book = _validated_curriculum_book(response)

    assert book.chapters[0].knowledge_points == ()
    assert len(book.chapters[1].knowledge_points) == 1
    assert book.chapters[1].knowledge_points[0].knowledge_key == "kp-counting-complete"
    point = book.chapters[1].knowledge_points[0]
    assert len(point.learning_objectives) == 10
    assert len(point.exercise_keys) == 30
    assert len(point.prerequisites) == 10


def test_newapi_provider_uses_safe_configured_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class Response:
        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self, _limit: int) -> bytes:
            return b"{}"

    def fake_urlopen(request: Any, *, timeout: float) -> Response:
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = NewApiVisionProvider(
        NewApiConfig(
            True,
            "https://newapi.local",
            "key",
            "vision-model",
            5,
            100_000,
            "study-api/0.5",
        )
    )

    assert provider._post_json({"model": "vision-model"}) == {}
    assert captured["timeout"] == 5
    assert captured["headers"]["User-agent"] == "study-api/0.5"
    assert captured["headers"]["Accept"] == "application/json"


def test_newapi_provider_retries_transient_gateway_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = NewApiVisionProvider(_config())
    calls = 0

    def fake_post_once(_payload: Mapping[str, Any]) -> Mapping[str, Any]:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise NewApiProviderError("temporary gateway failure", code="provider_http_5xx")
        return {"choices": []}

    monkeypatch.setattr(provider, "_post_json_once", fake_post_once)
    monkeypatch.setattr("study_api.newapi_provider.sleep", lambda _seconds: None)

    assert provider._post_json({"model": "vision-model"}) == {"choices": []}
    assert calls == 3


@pytest.mark.parametrize("user_agent", ("", "study-api/0.5\r\nX-Injected: true", "测验"))
def test_newapi_provider_rejects_unsafe_user_agent(user_agent: str) -> None:
    with pytest.raises(NewApiConfigurationError, match="USER_AGENT"):
        NewApiVisionProvider(
            NewApiConfig(
                True, "https://newapi.local", "key", "vision-model", 5, 100_000, user_agent
            )
        )


def test_newapi_provider_bounds_large_sanitized_image_before_base64_transport() -> None:
    source = Image.effect_noise((1800, 1400), 96).convert("RGB")
    source_buffer = io.BytesIO()
    source.save(source_buffer, format="PNG")
    source.close()
    image_bytes = source_buffer.getvalue()
    assert len(image_bytes) > 600_000

    provider = NewApiVisionProvider(_config())
    captured: dict[str, Any] = {}

    def fake_post(payload: dict[str, Any]) -> dict[str, Any]:
        captured.update(payload)
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"subject":"math","question_text":"synthetic",'
                            '"options":[],"formulas":[],"has_diagram":false,'
                            '"has_handwriting":false,"answer_state":"unclear",'
                            '"answer_state_confidence":0.4,"answer_steps":[],'
                            '"question_region_count":1,'
                            '"confidence":0.9,"needs_confirmation":true}'
                        )
                    }
                }
            ]
        }

    provider._post_json = fake_post  # type: ignore[method-assign]
    provider.analyze_sanitized_image(
        image_bytes, "image/png", sanitization_schema="privacy-sanitization.v1"
    )

    data_url = captured["messages"][1]["content"][1]["image_url"]["url"]
    assert data_url.startswith("data:image/jpeg;base64,")
    transported = base64.b64decode(data_url.split(",", maxsplit=1)[1])
    assert len(transported) <= 600_000
    assert transported.startswith(b"\xff\xd8\xff")


def test_newapi_provider_returns_validated_detailed_solution_without_image() -> None:
    provider = NewApiVisionProvider(_config())
    captured: dict[str, Any] = {}

    def fake_post(payload: dict[str, Any]) -> dict[str, Any]:
        captured.update(payload)
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"steps":["先求一共飞走多少只：6+12=18（只）",'
                            '"再求剩下多少只：35-18=17（只）"],'
                            '"final_answer":"还剩17只",'
                            '"verification":"17+6+12=35，与原数相同"}'
                        )
                    }
                }
            ]
        }

    provider._post_json = fake_post  # type: ignore[method-assign]
    result = provider.create_detailed_solution(
        question_text="原来有35只，飞走6只，又飞走12只，还剩多少只？",
        answer_state="blank",
        answer_text=None,
        answer_steps=(),
        curriculum_scope={
            "knowledge_key": "kp-subtraction",
            "title": "两步减法解决问题",
            "learning_objectives": ["先合并两次减少量，再求剩余"],
            "allowed_prerequisites": ["20 以内加减法"],
            "source_pages": [18],
        },
    )

    assert result.final_answer == "还剩17只"
    assert len(result.steps) == 2
    assert "image_url" not in str(captured)
    user_payload = json.loads(captured["messages"][1]["content"])
    assert user_payload["curriculum_grounding"] == "approved"
    assert user_payload["approved_curriculum_scope"]["knowledge_key"] == "kp-subtraction"


def test_newapi_provider_solves_unmatched_questions_without_claiming_a_source() -> None:
    provider = NewApiVisionProvider(_config())
    captured: dict[str, Any] = {}

    def fake_post(payload: dict[str, Any]) -> dict[str, Any]:
        captured.update(payload)
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"steps":["先看图中哪一段表示已经看过的页数。",'
                            '"用总页数减去已经看过的页数表示剩余页数。"],'
                            '"final_answer":"剩下的页数=总页数-已经看过的页数。",'
                            '"verification":"已经看过的页数加上剩余页数应等于总页数。"}'
                        )
                    }
                }
            ]
        }

    provider._post_json = fake_post  # type: ignore[method-assign]
    result = provider.create_detailed_solution(
        question_text="根据线段图，剩下的页数该怎么表示？",
        answer_state="blank",
        answer_text=None,
        answer_steps=(),
        curriculum_scope=None,
    )

    assert result.final_answer == "剩下的页数=总页数-已经看过的页数。"
    assert "image_url" not in str(captured)
    user_payload = json.loads(captured["messages"][1]["content"])
    assert user_payload["curriculum_grounding"] == "not_matched"
    assert user_payload["approved_curriculum_scope"] is None


def test_newapi_provider_plans_only_from_bounded_source_candidates() -> None:
    provider = NewApiVisionProvider(_config())
    captured: dict[str, Any] = {}
    source = RecommendationSource(
        source_key="curriculum:source-1:0",
        source_type="curriculum",
        question_text="三名同学同时阅读了20分钟，每人阅读了多长时间？",
        knowledge_point="同时发生与经过时间",
        snapshot_id=UUID("00000000-0000-0000-0000-000000000201"),
        curriculum_chunk_id=UUID("00000000-0000-0000-0000-000000000301"),
        source_title="经过时间",
        source_page=35,
        mistake_frequency=2,
        local_score=99,
    )

    def fake_post(payload: dict[str, Any]) -> dict[str, Any]:
        captured.update(payload)
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"items":[{"source_keys":["curriculum:source-1:0"],'
                            '"title":"经过时间巩固","reason":"练习教材第35页同类题",'
                            '"knowledge_point":"同时发生与经过时间",'
                            '"scheduled_offset_days":1,"estimated_minutes":10}]}'
                        )
                    }
                }
            ]
        }

    provider._post_json = fake_post  # type: ignore[method-assign]
    plan = provider.create_recommendation_plan(sources=(source,))

    assert plan.items[0].source_keys == ("curriculum:source-1:0",)
    request_payload = json.loads(captured["messages"][1]["content"])
    assert request_payload["source_candidates"][0]["source_page"] == 35
    assert "image_url" not in str(captured)
    assert "source_key values present" in captured["messages"][0]["content"]


def test_newapi_provider_understands_page_image_then_consolidates_book() -> None:
    provider = NewApiVisionProvider(_config())
    calls: list[dict[str, Any]] = []
    image = Image.new("RGB", (80, 60), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    image.close()

    def fake_post(payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(payload)
        if len(calls) == 1:
            content = {
                "schema_version": "curriculum-page-analysis.v1",
                "pages": [
                    {
                        "page_number": 14,
                        "chapter_title": "位置",
                        "section_title": None,
                        "summary": "借助图片认识物体之间的位置。",
                        "knowledge_observations": [
                            {
                                "title": "上下位置",
                                "summary": "根据两个物体判断上下关系。",
                                "prerequisites": [],
                                "exercises": [
                                    {
                                        "question_text": "苹果的下面是什么？",
                                        "visual_description": "苹果在书本上方，小熊在书本下方",
                                        "requires_visual_context": True,
                                        "difficulty": "基础题",
                                        "confidence": "92%",
                                    }
                                ],
                                "confidence": "90分",
                            }
                        ],
                        "confidence": 91,
                    }
                ],
            }
        else:
            content = {
                "schema_version": "curriculum-book-analysis.v1",
                "book_summary": "本册从位置关系开始建立数学表达。",
                "chapters": [
                    {
                        "title": "位置",
                        "start_page": 14,
                        "end_page": 14,
                        "summary": "认识上下前后。",
                        "knowledge_points": [
                            {
                                "knowledge_key": "kp-position-up-down",
                                "section_title": "上下前后",
                                "title": "判断上下位置",
                                "summary": "以参照物判断物体的上下关系。",
                                "learning_objectives": ["正确描述上下位置"],
                                "prerequisites": [],
                                "page_numbers": [14],
                                "exercise_keys": ["page:14:observation:0:exercise:0"],
                                "confidence": "91%",
                            }
                        ],
                    }
                ],
            }
        return {"choices": [{"message": {"content": json.dumps(content)}}]}

    provider._post_json = fake_post  # type: ignore[method-assign]
    pages = provider.analyze_curriculum_pages(
        (
            CurriculumProviderPage(
                page_number=14,
                extracted_text="位置 上下前后",
                image_bytes=buffer.getvalue(),
            ),
        )
    )
    book = provider.consolidate_curriculum_book(
        page_observations=(
            {
                **pages[0].model_dump(mode="json"),
                "exercise_keys": ["page:14:observation:0:exercise:0"],
            },
        )
    )

    assert pages[0].knowledge_observations[0].exercises[0].requires_visual_context
    assert pages[0].knowledge_observations[0].learning_objectives == ()
    assert pages[0].section_title == "位置"
    assert pages[0].knowledge_observations[0].exercises[0].difficulty == "basic"
    assert pages[0].knowledge_observations[0].exercises[0].confidence == 0.92
    assert pages[0].confidence == 0.91
    assert book.chapters[0].knowledge_points[0].page_numbers == (14,)
    assert book.chapters[0].knowledge_points[0].confidence == 0.91
    transported = calls[0]["messages"][1]["content"]
    assert any(block["type"] == "image_url" for block in transported)
    assert "extracted_text" in transported[0]["text"]
    assert (
        "difficulty must be exactly one of basic, medium, advanced"
        in calls[0]["messages"][0]["content"]
    )
    assert (
        "Every confidence must be a JSON number from 0 to 1" in calls[0]["messages"][0]["content"]
    )
    assert "repeat its chapter_title as section_title" in calls[0]["messages"][0]["content"]
    page_format = calls[0]["response_format"]
    assert page_format["type"] == "json_schema"
    assert page_format["json_schema"]["name"] == "curriculum_page_analysis"
    assert page_format["json_schema"]["schema"]["title"] == "ProviderPageAnalysisBatch"
    book_format = calls[1]["response_format"]
    assert book_format["type"] == "json_schema"
    assert book_format["json_schema"]["name"] == "curriculum_book_analysis"
    assert book_format["json_schema"]["schema"]["title"] == "ProviderBookAnalysis"


def test_newapi_provider_uses_chinese_v2_schema_and_short_passage_boundaries() -> None:
    provider = NewApiVisionProvider(_config())
    calls: list[dict[str, Any]] = []
    image = Image.new("RGB", (20, 20), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    image.close()

    def fake_post(payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(payload)
        content: dict[str, Any]
        if len(calls) == 1:
            content = {
                "schema_version": "chinese-curriculum-page-analysis.v2",
                "pages": [
                    {
                        "page_number": 1,
                        "chapter_title": "第一单元",
                        "section_title": "识字",
                        "summary": "观察拼音和生字。",
                        "knowledge_observations": [],
                        "passages": [
                            {
                                "title": "春晓",
                                "start_marker": "春眠",
                                "end_marker": "花落",
                                "kind": "poem",
                                "confidence": 0.9,
                                "lines": [
                                    "春眠不觉晓",
                                    "处处闻啼鸟",
                                    "夜来风雨声",
                                    "花落知多少",
                                ],
                            }
                        ],
                        "confidence": 0.9,
                    }
                ],
            }
        else:
            content = {
                "schema_version": "chinese-curriculum-book-analysis.v2",
                "book_summary": "识字与古诗文积累。",
                "chapters": [
                    {
                        "title": "第一单元",
                        "start_page": 1,
                        "end_page": 1,
                        "summary": "识字。",
                        "knowledge_points": [],
                    }
                ],
            }
        return {"choices": [{"message": {"content": json.dumps(content)}}]}

    provider._post_json = fake_post  # type: ignore[method-assign]
    pages = provider.analyze_curriculum_pages(
        (
            CurriculumProviderPage(
                page_number=1, extracted_text="synthetic-only", image_bytes=buffer.getvalue()
            ),
        ),
        subject=Subject.CHINESE,
    )
    book = provider.consolidate_curriculum_book(
        page_observations=tuple(page.model_dump(mode="json") for page in pages),
        subject=Subject.CHINESE,
    )

    assert pages[0].passages[0].kind == "poem"
    assert book.schema_version == "chinese-curriculum-book-analysis.v2"
    assert calls[0]["response_format"]["json_schema"]["schema"]["title"] == (
        "ChineseProviderPageAnalysisBatch"
    )
    assert "short visible boundary markers" in calls[0]["messages"][0]["content"]


def test_curriculum_schema_failure_logs_only_safe_validation_metadata(
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider = NewApiVisionProvider(_config())
    image = Image.new("RGB", (20, 20), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    image.close()
    provider._post_json = lambda _payload: {  # type: ignore[method-assign]
        "choices": [
            {
                "message": {
                    "content": (
                        '{"schema_version":"curriculum-page-analysis.v1",'
                        '"pages":[{"summary":"教材私密内容"}]}'
                    )
                }
            }
        ]
    }

    with caplog.at_level(logging.WARNING, logger="study_api.newapi_provider"):
        with pytest.raises(NewApiProviderError, match="curriculum page schema") as error:
            provider.analyze_curriculum_pages(
                (
                    CurriculumProviderPage(
                        page_number=1,
                        extracted_text="synthetic-only",
                        image_bytes=buffer.getvalue(),
                    ),
                )
            )

    assert error.value.code == "provider_curriculum_page_schema_invalid"
    assert "curriculum_provider_schema_invalid" in caplog.text
    assert "validation_error" in caplog.text
    assert "教材私密内容" not in caplog.text


def test_curriculum_pages_fall_back_when_gateway_rejects_json_schema() -> None:
    provider = NewApiVisionProvider(_config())
    calls: list[dict[str, Any]] = []
    image = Image.new("RGB", (20, 20), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    image.close()

    def fake_post(payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(payload)
        if len(calls) == 1:
            raise NewApiProviderError("unsupported response format", code="provider_http_400")
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"schema_version":"curriculum-page-analysis.v1",'
                            '"pages":[{"page_number":1,"chapter_title":"第一单元",'
                            '"section_title":"位置","summary":"认识位置。",'
                            '"knowledge_observations":[],"confidence":0.9}]}'
                        )
                    }
                }
            ]
        }

    provider._post_json = fake_post  # type: ignore[method-assign]
    pages = provider.analyze_curriculum_pages(
        (
            CurriculumProviderPage(
                page_number=1,
                extracted_text="synthetic-only",
                image_bytes=buffer.getvalue(),
            ),
        )
    )

    assert len(pages) == 1
    assert calls[0]["response_format"]["type"] == "json_schema"
    assert calls[1]["response_format"] == {"type": "json_object"}


def test_curriculum_pages_omit_response_format_when_gateway_rejects_json_object() -> None:
    provider = NewApiVisionProvider(_config())
    calls: list[dict[str, Any]] = []
    image = Image.new("RGB", (20, 20), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    image.close()

    def fake_post(payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(payload)
        if len(calls) < 3:
            raise NewApiProviderError("unsupported response format", code="provider_http_400")
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"schema_version":"curriculum-page-analysis.v1",'
                            '"pages":[{"page_number":1,"chapter_title":"第一单元",'
                            '"section_title":"位置","summary":"认识位置。",'
                            '"knowledge_observations":[],"confidence":0.9}]}'
                        )
                    }
                }
            ]
        }

    provider._post_json = fake_post  # type: ignore[method-assign]
    pages = provider.analyze_curriculum_pages(
        (
            CurriculumProviderPage(
                page_number=1,
                extracted_text="synthetic-only",
                image_bytes=buffer.getvalue(),
            ),
        )
    )

    assert len(pages) == 1
    assert calls[0]["response_format"]["type"] == "json_schema"
    assert calls[1]["response_format"] == {"type": "json_object"}
    assert "response_format" not in calls[2]
