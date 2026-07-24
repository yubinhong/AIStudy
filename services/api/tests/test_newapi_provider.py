import base64
import io
import json
from typing import Any
from uuid import UUID

import pytest
from PIL import Image

from study_api.newapi_provider import (
    CurriculumProviderPage,
    NewApiConfig,
    NewApiConfigurationError,
    NewApiProviderError,
    NewApiVisionProvider,
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


def test_newapi_provider_bounds_whole_book_observation_payload() -> None:
    provider = NewApiVisionProvider(_config())

    with pytest.raises(NewApiProviderError, match="bounded input") as error:
        provider.consolidate_curriculum_book(page_observations=({"summary": "x" * 2_000_001},))

    assert error.value.code == "provider_curriculum_book_input_too_large"


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
    )

    assert result.final_answer == "还剩17只"
    assert len(result.steps) == 2
    assert "image_url" not in str(captured)


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
                        "section_title": "上下前后",
                        "summary": "借助图片认识物体之间的位置。",
                        "knowledge_observations": [
                            {
                                "title": "上下位置",
                                "summary": "根据两个物体判断上下关系。",
                                "learning_objectives": ["能说出谁在谁的上面"],
                                "prerequisites": [],
                                "exercises": [
                                    {
                                        "question_text": "苹果的下面是什么？",
                                        "visual_description": "苹果在书本上方，小熊在书本下方",
                                        "requires_visual_context": True,
                                        "difficulty": "basic",
                                        "confidence": 0.92,
                                    }
                                ],
                                "confidence": 0.9,
                            }
                        ],
                        "confidence": 0.91,
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
                                "confidence": 0.91,
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
    assert book.chapters[0].knowledge_points[0].page_numbers == (14,)
    transported = calls[0]["messages"][1]["content"]
    assert any(block["type"] == "image_url" for block in transported)
    assert "extracted_text" in transported[0]["text"]
