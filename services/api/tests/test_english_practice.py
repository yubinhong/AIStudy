from uuid import UUID

import pytest
from auth_helpers import session_headers
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from study_api.english_practice import (
    EnglishLevel,
    EnglishLiveConfig,
    EnglishLiveSession,
    FakeEnglishLiveProvider,
    InMemoryEnglishPracticeRepository,
    build_english_provider,
)
from study_api.main import create_app

HOUSEHOLD_A = "00000000-0000-0000-0000-000000000001"
HOUSEHOLD_B = "00000000-0000-0000-0000-000000000002"
CHILD_A = "00000000-0000-0000-0000-000000000101"
CHILD_B = "00000000-0000-0000-0000-000000000102"
CONSENT = "english-audio-consent.v1"
CLIENT_SCHEMA = "english-live-client-event.v1"


class _CapturingFakeProvider(FakeEnglishLiveProvider):
    policy_instruction: str | None = None

    async def open_session(
        self, *, scenario_id: str, level: EnglishLevel, policy_instruction: str
    ) -> EnglishLiveSession:
        self.policy_instruction = policy_instruction
        return await super().open_session(
            scenario_id=scenario_id,
            level=level,
            policy_instruction=policy_instruction,
        )


class _FailingFakeProvider(FakeEnglishLiveProvider):
    async def open_session(
        self, *, scenario_id: str, level: EnglishLevel, policy_instruction: str
    ) -> EnglishLiveSession:
        del scenario_id, level, policy_instruction
        raise RuntimeError("synthetic provider failure")


def _client(
    *,
    daily_limit_seconds: int = 600,
    session_limit_seconds: int = 480,
    idle_timeout_seconds: int = 30,
    provider: FakeEnglishLiveProvider | None = None,
) -> TestClient:
    config = EnglishLiveConfig(
        enabled=True,
        provider="fake",
        allow_test_provider=True,
        daily_limit_seconds=daily_limit_seconds,
        session_limit_seconds=session_limit_seconds,
        idle_timeout_seconds=idle_timeout_seconds,
    )
    return TestClient(
        create_app(
            english_practice_repository=InMemoryEnglishPracticeRepository(),
            english_live_config=config,
            english_live_provider=provider or FakeEnglishLiveProvider(),
        )
    )


def _parent(client: TestClient) -> dict[str, str]:
    return session_headers(client, role="parent")


def _child(client: TestClient) -> dict[str, str]:
    return session_headers(client, role="child", child_id=CHILD_A)


def _enable(client: TestClient, key: str = "english-enable-001"):
    return client.put(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/english-practice/settings",
        headers={**_parent(client), "Idempotency-Key": key},
        json={
            "enabled": True,
            "level": "a1",
            "consent_version": CONSENT,
            "expected_version": 0,
        },
    )


def _start(client: TestClient, key: str = "english-start-001", scenario: str = "greetings"):
    return client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/english-practice/sessions",
        headers={**_child(client), "Idempotency-Key": key},
        json={"scenario_id": scenario},
    )


def test_default_provider_keeps_english_locked() -> None:
    client = TestClient(create_app())
    settings = client.get(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/english-practice/settings",
        headers=_parent(client),
    )
    enabling = client.put(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/english-practice/settings",
        headers={**_parent(client), "Idempotency-Key": "english-disabled-001"},
        json={
            "enabled": True,
            "level": "pre_a1",
            "consent_version": CONSENT,
            "expected_version": 0,
        },
    )

    assert settings.status_code == 200
    assert settings.json()["provider_available"] is False
    assert enabling.status_code == 409


def test_environment_cannot_enable_fake_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUDY_ENGLISH_LIVE_ENABLED", "true")
    monkeypatch.setenv("STUDY_ENGLISH_LIVE_PROVIDER", "fake")

    config = EnglishLiveConfig.from_environment()

    assert config.allow_test_provider is False
    assert config.provider_available is False
    assert build_english_provider(config).available is False


def test_parent_updates_settings_with_consent_version_and_idempotency() -> None:
    client = _client()

    first = _enable(client)
    replay = _enable(client)
    conflict = client.put(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/english-practice/settings",
        headers={**_parent(client), "Idempotency-Key": "english-enable-001"},
        json={
            "enabled": False,
            "level": "a2",
            "consent_version": None,
            "expected_version": 1,
        },
    )

    assert first.status_code == 200
    assert first.json()["level"] == "a1"
    assert first.json()["version"] == 1
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert conflict.status_code == 409


def test_child_cannot_change_settings_and_owner_scope_is_hidden() -> None:
    client = _client()
    child_update = client.put(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/english-practice/settings",
        headers={**_child(client), "Idempotency-Key": "child-cannot-enable"},
        json={
            "enabled": True,
            "level": "a1",
            "consent_version": CONSENT,
            "expected_version": 0,
        },
    )
    other_owner = client.get(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_B}/english-practice/settings",
        headers=_parent(client),
    )

    assert child_update.status_code == 403
    assert other_owner.status_code == 404


def test_cross_household_and_sibling_access_are_rejected() -> None:
    client = _client()
    cross_household = client.get(
        f"/households/{HOUSEHOLD_B}/children/{CHILD_A}/english-practice/settings",
        headers=_parent(client),
    )
    sibling = client.get(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_B}/english-practice/sessions",
        headers=_child(client),
    )

    assert cross_household.status_code == 404
    assert sibling.status_code == 404


def test_child_sees_three_scenarios_and_only_one_active_session() -> None:
    client = _client()
    assert _enable(client).status_code == 200

    scenarios = client.get(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/english-practice/scenarios",
        headers=_child(client),
    )
    started = _start(client)
    replay = _start(client)
    second = _start(client, key="english-start-002", scenario="school")

    assert [item["id"] for item in scenarios.json()] == ["greetings", "school", "food_order"]
    assert started.status_code == 201
    assert started.json()["provider"] == "fake"
    assert "transcript" not in started.json()
    assert replay.status_code == 200
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert second.status_code == 409


def test_daily_limit_blocks_start_before_provider_stream() -> None:
    client = _client(daily_limit_seconds=0)
    assert _enable(client).status_code == 200

    response = _start(client)

    assert response.status_code == 429


def test_complete_session_is_idempotent() -> None:
    client = _client()
    assert _enable(client).status_code == 200
    session_id = _start(client).json()["id"]
    path = (
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/english-practice/"
        f"sessions/{session_id}/complete"
    )
    headers = {**_child(client), "Idempotency-Key": "english-complete-001"}

    first = client.post(path, headers=headers, json={"status": "interrupted"})
    replay = client.post(path, headers=headers, json={"status": "interrupted"})

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.headers["Idempotency-Replayed"] == "true"

    conflicting_final = client.post(
        path,
        headers={**_child(client), "Idempotency-Key": "english-complete-002"},
        json={"status": "completed"},
    )
    assert conflicting_final.status_code == 409


def test_session_wall_and_idle_limits_finalize_activity() -> None:
    for client, reason in (
        (_client(session_limit_seconds=0), "session_limit"),
        (_client(idle_timeout_seconds=0), "idle_timeout"),
    ):
        assert _enable(client).status_code == 200
        session_id = _start(client).json()["id"]
        path = (
            f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/english-practice/"
            f"sessions/{session_id}/stream"
        )
        with client.websocket_connect(path, headers=_child(client)) as websocket:
            assert websocket.receive_json()["type"] == "ready"
            completed = websocket.receive_json()
        assert completed["type"] == "completed"
        assert completed["reason"] == reason


def test_session_log_excludes_identity_and_content(caplog: pytest.LogCaptureFixture) -> None:
    client = _client()
    assert _enable(client).status_code == 200

    with caplog.at_level("INFO", logger="study_api.routes.english_practice"):
        assert _start(client).status_code == 201

    record = next(item for item in caplog.records if item.message == "english_session_started")
    assert record.provider == "fake"
    assert record.model_version == "fake-english-live.v1"
    assert not hasattr(record, "child_id")
    assert not hasattr(record, "scenario_id")
    assert "transcript" not in record.getMessage()


def test_websocket_requires_child_bearer_and_accepts_pcm_contract() -> None:
    provider = _CapturingFakeProvider()
    client = _client(provider=provider)
    assert _enable(client).status_code == 200
    started = _start(client)
    session_id = UUID(started.json()["id"])
    path = (
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/english-practice/"
        f"sessions/{session_id}/stream"
    )

    with client.websocket_connect(path, headers=_child(client)) as websocket:
        assert websocket.receive_json()["type"] == "ready"
        websocket.send_json({"schema_version": CLIENT_SCHEMA, "type": "listening"})
        assert websocket.receive_json()["type"] == "listening"
        websocket.send_bytes(bytes(640))
        websocket.send_json({"schema_version": CLIENT_SCHEMA, "type": "audio_stream_end"})
        assert websocket.receive_json()["type"] == "thinking"
        assert websocket.receive_json()["type"] == "speaking"
        assert len(websocket.receive_bytes()) == 1920
        websocket.send_json({"schema_version": CLIENT_SCHEMA, "type": "complete"})
        assert websocket.receive_json()["type"] == "completed"

    summary = client.get(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/english-practice/sessions",
        headers=_parent(client),
    ).json()[0]
    assert summary["status"] == "completed"
    assert summary["turn_count"] == 1
    assert summary["input_audio_ms"] == 20
    assert summary["output_audio_ms"] == 40
    assert provider.policy_instruction is not None
    assert "Never request a name, school, address" in provider.policy_instruction


def test_provider_open_failure_finalizes_without_exposing_details() -> None:
    client = _client(provider=_FailingFakeProvider())
    assert _enable(client).status_code == 200
    session_id = _start(client).json()["id"]
    path = (
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/english-practice/"
        f"sessions/{session_id}/stream"
    )

    with client.websocket_connect(path, headers=_child(client)) as websocket:
        error = websocket.receive_json()

    assert error["type"] == "error"
    assert error["code"] == "provider_unavailable"
    assert "synthetic" not in str(error)
    summary = client.get(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/english-practice/sessions",
        headers=_parent(client),
    ).json()[0]
    assert summary["status"] == "failed"
    assert summary["failure_code"] == "provider_stream_failed"


def test_websocket_rejects_non_20_or_40_ms_audio_frame() -> None:
    client = _client()
    assert _enable(client).status_code == 200
    session_id = _start(client).json()["id"]
    path = (
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/english-practice/"
        f"sessions/{session_id}/stream"
    )

    with client.websocket_connect(path, headers=_child(client)) as websocket:
        assert websocket.receive_json()["type"] == "ready"
        websocket.send_bytes(bytes(100))
        assert websocket.receive_json()["code"] == "invalid_audio_frame"
        with pytest.raises(WebSocketDisconnect):
            websocket.receive_json()

    summary = client.get(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/english-practice/sessions",
        headers=_child(client),
    ).json()[0]
    assert summary["status"] == "interrupted"


def test_websocket_stops_after_session_revocation() -> None:
    client = _client()
    assert _enable(client).status_code == 200
    session_id = _start(client).json()["id"]
    headers = _child(client)
    token = headers["Authorization"].removeprefix("Bearer ")
    path = (
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/english-practice/"
        f"sessions/{session_id}/stream"
    )

    with client.websocket_connect(path, headers=headers) as websocket:
        assert websocket.receive_json()["type"] == "ready"
        _, auth_session = client.app.state.auth_service.authenticate(token)
        client.app.state.auth_service.logout(auth_session)
        websocket.send_json({"schema_version": CLIENT_SCHEMA, "type": "listening"})
        assert websocket.receive_json()["type"] == "listening"
        revoked = websocket.receive_json()
        assert revoked["type"] == "error"
        assert revoked["code"] == "session_revoked"

    summary = client.get(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/english-practice/sessions",
        headers=_parent(client),
    ).json()[0]
    assert summary["status"] == "interrupted"


def test_websocket_rejects_control_without_schema_version() -> None:
    client = _client()
    assert _enable(client).status_code == 200
    session_id = _start(client).json()["id"]
    path = (
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/english-practice/"
        f"sessions/{session_id}/stream"
    )

    with client.websocket_connect(path, headers=_child(client)) as websocket:
        assert websocket.receive_json()["type"] == "ready"
        websocket.send_json({"type": "listening"})
        invalid = websocket.receive_json()

    assert invalid["type"] == "error"
    assert invalid["code"] == "invalid_control"
