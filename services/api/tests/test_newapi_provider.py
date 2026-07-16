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
    provider._post_json = lambda _: {  # type: ignore[method-assign]
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
    result = provider.analyze_sanitized_image(
        b"synthetic", "image/png", sanitization_schema="privacy-sanitization.v1"
    )
    assert result.subject == "math"
    assert result.needs_confirmation is True


def test_newapi_provider_rejects_invalid_response_and_unsafe_config() -> None:
    with pytest.raises(NewApiConfigurationError):
        NewApiVisionProvider(NewApiConfig(True, "", "", "", 0, 1))
    provider = NewApiVisionProvider(_config())
    provider._post_json = lambda _: {"choices": []}  # type: ignore[method-assign]
    with pytest.raises(NewApiProviderError):
        provider.analyze_sanitized_image(b"synthetic", "image/png", sanitization_schema="v1")
