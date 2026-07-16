"""Small self-hosted household bearer token format.

This is intentionally an application token for one self-hosted household, not
an identity provider. Tokens are signed, expiry-bound, and contain no child
name, email, image, or learning content.
"""

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from study_api.domain.models import DemoRole


class AuthTokenError(ValueError):
    """Raised when a self-hosted bearer token is invalid or expired."""


@dataclass(frozen=True)
class AuthTokenClaims:
    household_id: UUID
    role: DemoRole
    child_id: UUID | None
    expires_at: datetime


def issue_token(
    secret: str,
    household_id: UUID,
    role: DemoRole,
    child_id: UUID | None = None,
    *,
    ttl: timedelta = timedelta(days=30),
) -> str:
    if len(secret) < 32:
        raise AuthTokenError("STUDY_AUTH_SECRET must contain at least 32 characters")
    if role is DemoRole.CHILD and child_id is None:
        raise AuthTokenError("child tokens require child_id")
    if role is DemoRole.PARENT and child_id is not None:
        raise AuthTokenError("parent tokens cannot contain child_id")
    now = datetime.now(UTC)
    expires_at = now + ttl
    payload: dict[str, Any] = {
        "v": 1,
        "jti": secrets.token_hex(12),
        "household_id": str(household_id),
        "role": role.value,
        "child_id": str(child_id) if child_id else None,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    encoded = _encode_json(payload)
    signature = _sign(secret, encoded)
    return f"st1.{encoded}.{signature}"


def parse_token(secret: str, token: str, *, now: datetime | None = None) -> AuthTokenClaims:
    if len(secret) < 32:
        raise AuthTokenError("STUDY_AUTH_SECRET is not configured safely")
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != "st1":
        raise AuthTokenError("invalid bearer token")
    encoded, signature = parts[1], parts[2]
    expected = _sign(secret, encoded)
    if not hmac.compare_digest(signature, expected):
        raise AuthTokenError("invalid bearer token")
    try:
        payload = json.loads(_decode_json(encoded))
        household_id = UUID(payload["household_id"])
        role = DemoRole(payload["role"])
        child_id = UUID(payload["child_id"]) if payload.get("child_id") else None
        expires_at = datetime.fromtimestamp(int(payload["exp"]), UTC)
        version = int(payload["v"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise AuthTokenError("invalid bearer token") from error
    if version != 1 or (role is DemoRole.CHILD) != (child_id is not None):
        raise AuthTokenError("invalid bearer token claims")
    current_time = now or datetime.now(UTC)
    if expires_at <= current_time:
        raise AuthTokenError("bearer token expired")
    return AuthTokenClaims(household_id, role, child_id, expires_at)


def _encode_json(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return _b64(raw)


def _decode_json(encoded: str) -> str:
    try:
        return base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
    except (ValueError, UnicodeDecodeError) as error:
        raise AuthTokenError("invalid bearer token") from error


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _sign(secret: str, encoded: str) -> str:
    digest = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).digest()
    return _b64(digest)
