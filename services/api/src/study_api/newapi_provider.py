"""Provider-neutral OpenAI-compatible adapter for a self-hosted NewAPI gateway.

The adapter is disabled unless explicitly configured. It accepts only the
already-confirmed sanitized derivative for vision analysis and validates the
structured response before returning it to business code. Raw request/response
content is never logged or persisted by this module.
"""

import base64
import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from study_api.privacy_models import QuestionExtraction


class NewApiConfigurationError(RuntimeError):
    """Raised when self-hosted Provider configuration is incomplete or unsafe."""


class NewApiProviderError(RuntimeError):
    """Raised when the configured gateway cannot return a safe response."""


@dataclass(frozen=True)
class NewApiConfig:
    enabled: bool
    base_url: str
    api_key: str
    vision_model: str
    timeout_seconds: float
    max_response_bytes: int

    @classmethod
    def from_environment(cls) -> "NewApiConfig":
        enabled = os.environ.get("STUDY_NEWAPI_ENABLED", "false").lower() == "true"
        config = cls(
            enabled=enabled,
            base_url=os.environ.get("STUDY_NEWAPI_BASE_URL", "").rstrip("/"),
            api_key=os.environ.get("STUDY_NEWAPI_API_KEY", ""),
            vision_model=os.environ.get("STUDY_NEWAPI_VISION_MODEL", ""),
            timeout_seconds=float(os.environ.get("STUDY_NEWAPI_TIMEOUT_SECONDS", "30")),
            max_response_bytes=int(os.environ.get("STUDY_NEWAPI_MAX_RESPONSE_BYTES", "262144")),
        )
        if config.enabled:
            config.validate()
        return config

    def validate(self) -> None:
        if not self.base_url.startswith(("http://", "https://")):
            raise NewApiConfigurationError("STUDY_NEWAPI_BASE_URL must be an HTTP(S) URL")
        if not self.api_key or len(self.api_key) > 512:
            raise NewApiConfigurationError(
                "STUDY_NEWAPI_API_KEY is required when NewAPI is enabled"
            )
        if not self.vision_model or len(self.vision_model) > 160:
            raise NewApiConfigurationError("STUDY_NEWAPI_VISION_MODEL is required")
        if not 1 <= self.timeout_seconds <= 120:
            raise NewApiConfigurationError("STUDY_NEWAPI_TIMEOUT_SECONDS must be between 1 and 120")
        if not 4_096 <= self.max_response_bytes <= 4_000_000:
            raise NewApiConfigurationError(
                "STUDY_NEWAPI_MAX_RESPONSE_BYTES is outside the safe range"
            )


class NewApiVisionProvider:
    """Call the configured OpenAI-compatible chat completion endpoint."""

    def __init__(self, config: NewApiConfig) -> None:
        config.validate()
        self._config = config

    def analyze_sanitized_image(
        self, image_bytes: bytes, media_type: str, *, sanitization_schema: str
    ) -> QuestionExtraction:
        if media_type not in {"image/jpeg", "image/png"}:
            raise NewApiProviderError("unsupported sanitized image type")
        if not 1 <= len(image_bytes) <= 8_000_000:
            raise NewApiProviderError("sanitized image size is outside the allowed range")
        payload = {
            "model": self._config.vision_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return only a JSON object matching question-extraction.v1. "
                        "Do not provide a solution or direct answer. "
                        f"Sanitization schema: {sanitization_schema}."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract one math question for human confirmation.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": (
                                    f"data:{media_type};base64,"
                                    f"{base64.b64encode(image_bytes).decode()}"
                                )
                            },
                        },
                    ],
                },
            ],
        }
        response = self._post_json(payload)
        try:
            content = _completion_content(response)
            parsed = json.loads(_strip_code_fence(content))
            return QuestionExtraction.model_validate(parsed)
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise NewApiProviderError(
                "Provider response failed question schema validation"
            ) from error

    def _post_json(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        request = urllib.request.Request(
            _chat_completions_url(self._config.base_url),
            data=json.dumps(payload, separators=(",", ":")).encode(),
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._config.timeout_seconds) as response:
                body = response.read(self._config.max_response_bytes + 1)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            raise NewApiProviderError("self-hosted Provider request failed") from error
        if len(body) > self._config.max_response_bytes:
            raise NewApiProviderError("self-hosted Provider response is too large")
        try:
            parsed = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise NewApiProviderError("self-hosted Provider response is not JSON") from error
        if not isinstance(parsed, Mapping):
            raise NewApiProviderError("self-hosted Provider response has an invalid shape")
        return parsed


def _completion_content(payload: Mapping[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("missing choices")
    first = choices[0]
    if not isinstance(first, Mapping) or not isinstance(first.get("message"), Mapping):
        raise ValueError("missing message")
    content = first["message"].get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts: list[str] = []
        for item in content:
            if not isinstance(item, Mapping) or not isinstance(item.get("text"), str):
                raise ValueError("invalid message content block")
            texts.append(item["text"])
        if texts:
            return "".join(texts)
    raise ValueError("missing message content")


def _chat_completions_url(base_url: str) -> str:
    return (
        f"{base_url}/chat/completions"
        if base_url.rstrip("/").endswith("/v1")
        else f"{base_url}/v1/chat/completions"
    )


def _strip_code_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        stripped = stripped[3:-3].strip()
        if stripped.startswith("json"):
            stripped = stripped[4:].lstrip()
    return stripped
