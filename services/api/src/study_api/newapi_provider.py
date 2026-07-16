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

QUESTION_EXTRACTION_INSTRUCTIONS = (
    "Return only one JSON object with no Markdown, explanation, or extra keys. "
    "It must conform to question-extraction.v1: schema_version must be "
    "'question-extraction.v1'; subject must be 'math'; question_text must be the "
    "question only; options and formulas must be arrays of strings; has_diagram and "
    "has_handwriting must be booleans; question_region_count must be an integer from "
    "0 to 256; confidence must be a number from 0 to 1; and needs_confirmation must "
    "be true. Do not add fields. Never solve the question or infer an answer; omit "
    "the optional detected_answer field."
)


class NewApiConfigurationError(RuntimeError):
    """Raised when self-hosted Provider configuration is incomplete or unsafe."""


class NewApiProviderError(RuntimeError):
    """Raised when the configured gateway cannot return a safe response."""

    def __init__(self, message: str, *, code: str = "provider_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class NewApiConfig:
    enabled: bool
    base_url: str
    api_key: str
    vision_model: str
    timeout_seconds: float
    max_response_bytes: int
    user_agent: str = "study-api/0.5"

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
            user_agent=os.environ.get("STUDY_NEWAPI_USER_AGENT", "study-api/0.5"),
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
        if not 1 <= len(self.user_agent) <= 256 or any(
            not 32 <= ord(character) <= 126 for character in self.user_agent
        ):
            raise NewApiConfigurationError(
                "STUDY_NEWAPI_USER_AGENT must be printable ASCII without control characters"
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
                        f"{QUESTION_EXTRACTION_INSTRUCTIONS} "
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
                "Provider response failed question schema validation",
                code="provider_response_schema_invalid",
            ) from error

    def _post_json(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        request = urllib.request.Request(
            _chat_completions_url(self._config.base_url),
            data=json.dumps(payload, separators=(",", ":")).encode(),
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": self._config.user_agent,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._config.timeout_seconds) as response:
                body = response.read(self._config.max_response_bytes + 1)
        except urllib.error.HTTPError as error:
            code = (
                f"provider_http_{error.code}" if 400 <= error.code <= 499 else "provider_http_5xx"
            )
            raise NewApiProviderError("self-hosted Provider request failed", code=code) from error
        except urllib.error.URLError as error:
            raise NewApiProviderError(
                "self-hosted Provider network request failed", code="provider_network_error"
            ) from error
        except TimeoutError as error:
            raise NewApiProviderError(
                "self-hosted Provider request timed out", code="provider_timeout"
            ) from error
        if len(body) > self._config.max_response_bytes:
            raise NewApiProviderError(
                "self-hosted Provider response is too large", code="provider_response_too_large"
            )
        try:
            parsed = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise NewApiProviderError(
                "self-hosted Provider response is not JSON", code="provider_response_not_json"
            ) from error
        if not isinstance(parsed, Mapping):
            raise NewApiProviderError(
                "self-hosted Provider response has an invalid shape",
                code="provider_response_invalid_shape",
            )
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
