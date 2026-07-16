from typing import Any

import pytest

from study_api.newapi_provider import (
    NewApiConfig,
    NewApiConfigurationError,
    NewApiProviderError,
    NewApiVisionProvider,
)


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
                            '"has_handwriting":false,"question_region_count":1,'
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
    assert result.needs_confirmation is True
    system_prompt = captured["messages"][0]["content"]
    for field in (
        "schema_version",
        "question_text",
        "options",
        "formulas",
        "has_diagram",
        "has_handwriting",
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
