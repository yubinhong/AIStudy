from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from study_api.auth import get_demo_principal
from study_api.auth_tokens import AuthTokenError, issue_token, parse_token
from study_api.domain.models import DemoRole

SECRET = "s" * 48
HOUSEHOLD = UUID("00000000-0000-0000-0000-000000000001")
CHILD = UUID("00000000-0000-0000-0000-000000000101")


def test_bearer_token_round_trip_contains_only_scoped_claims() -> None:
    token = issue_token(SECRET, HOUSEHOLD, DemoRole.CHILD, CHILD)
    claims = parse_token(SECRET, token)
    assert claims.household_id == HOUSEHOLD
    assert claims.role is DemoRole.CHILD
    assert claims.child_id == CHILD


def test_bearer_token_rejects_tampering_and_expiry() -> None:
    token = issue_token(SECRET, HOUSEHOLD, DemoRole.PARENT, ttl=timedelta(seconds=1))
    with pytest.raises(AuthTokenError):
        parse_token(SECRET, token[:-1] + ("a" if token[-1] != "a" else "b"))
    with pytest.raises(AuthTokenError, match="expired"):
        parse_token(SECRET, token, now=datetime.now(UTC) + timedelta(minutes=1))


def test_fastapi_principal_accepts_self_hosted_bearer_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = issue_token(SECRET, HOUSEHOLD, DemoRole.PARENT)
    monkeypatch.setenv("STUDY_AUTH_SECRET", SECRET)
    principal = get_demo_principal(authorization=f"Bearer {token}")
    assert principal.household_id == HOUSEHOLD
    assert principal.role is DemoRole.PARENT
