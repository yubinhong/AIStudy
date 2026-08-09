"""Household-scoped English speaking settings, summaries and live relay."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, WebSocket
from fastapi.responses import JSONResponse
from starlette.websockets import WebSocketDisconnect

from study_api.auth import (
    AuthenticatedPrincipal,
    _bearer_token,
    get_principal,
    require_bound_child,
    require_household,
    require_parent,
)
from study_api.domain.models import AccountRole
from study_api.domain.repository import IdempotencyConflictError, ProfileRepository
from study_api.english_practice import (
    ENGLISH_SCENARIOS,
    CompleteEnglishSessionRequest,
    EnglishActiveSessionError,
    EnglishConsentRequiredError,
    EnglishConversationPolicy,
    EnglishLiveConfig,
    EnglishLiveProvider,
    EnglishLiveSession,
    EnglishPracticeDisabledError,
    EnglishPracticeRepository,
    EnglishPracticeSession,
    EnglishPracticeSettingsView,
    EnglishScenario,
    EnglishSessionFinalizedError,
    EnglishSessionLimitError,
    EnglishSessionStatus,
    SettingsVersionConflictError,
    StartEnglishSessionRequest,
    UpdateEnglishPracticeSettings,
)

router = APIRouter(
    prefix="/households/{household_id}/children/{child_id}/english-practice",
    tags=["english-practice"],
)
logger = logging.getLogger(__name__)
Principal = Annotated[AuthenticatedPrincipal, Depends(get_principal)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


def _repository(request: Request) -> EnglishPracticeRepository:
    return request.app.state.english_practice_repository


def _profile_repository(request: Request) -> ProfileRepository:
    return request.app.state.profile_repository


Repository = Annotated[EnglishPracticeRepository, Depends(_repository)]
Profiles = Annotated[ProfileRepository, Depends(_profile_repository)]


def _authorize_child(
    household_id: UUID,
    child_id: UUID,
    principal: AuthenticatedPrincipal,
    profiles: ProfileRepository,
    *,
    parent_only: bool = False,
) -> None:
    role = require_household(principal, household_id)
    child = profiles.get_child(household_id, child_id)
    if child is None:
        raise HTTPException(status_code=404, detail="resource not found")
    if role is AccountRole.CHILD:
        if parent_only:
            require_parent(role)
        if require_bound_child(principal) != child_id:
            raise HTTPException(status_code=404, detail="resource not found")
    elif child.owner_account_id != principal.account_id:
        raise HTTPException(status_code=404, detail="resource not found")
    if parent_only:
        require_parent(role)


def _settings_view(request: Request, settings) -> EnglishPracticeSettingsView:
    config: EnglishLiveConfig = request.app.state.english_live_config
    provider: EnglishLiveProvider = request.app.state.english_live_provider
    return EnglishPracticeSettingsView(
        **settings.model_dump(),
        provider_available=config.provider_available and provider.available,
        required_consent_version=config.consent_version,
    )


@router.get("/settings", response_model=EnglishPracticeSettingsView)
def get_settings(
    household_id: UUID,
    child_id: UUID,
    principal: Principal,
    request: Request,
    repository: Repository,
    profiles: Profiles,
) -> EnglishPracticeSettingsView:
    _authorize_child(household_id, child_id, principal, profiles)
    return _settings_view(request, repository.get_settings(household_id, child_id))


@router.put("/settings", response_model=EnglishPracticeSettingsView)
def update_settings(
    household_id: UUID,
    child_id: UUID,
    body: UpdateEnglishPracticeSettings,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    request: Request,
    repository: Repository,
    profiles: Profiles,
) -> JSONResponse:
    _authorize_child(household_id, child_id, principal, profiles, parent_only=True)
    config: EnglishLiveConfig = request.app.state.english_live_config
    provider: EnglishLiveProvider = request.app.state.english_live_provider
    if body.enabled and (not config.provider_available or not provider.available):
        raise HTTPException(status_code=409, detail="english live provider is unavailable")
    if body.enabled and body.consent_version != config.consent_version:
        raise HTTPException(status_code=409, detail="current guardian consent is required")
    try:
        settings, replayed = repository.update_settings(
            household_id, child_id, principal.account_id, body, idempotency_key
        )
    except SettingsVersionConflictError as error:
        raise HTTPException(status_code=409, detail="settings version conflict") from error
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=409, detail="idempotency key reused with a different payload"
        ) from error
    view = _settings_view(request, settings)
    return JSONResponse(
        content=view.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


@router.get("/scenarios", response_model=list[EnglishScenario])
def list_scenarios(
    household_id: UUID,
    child_id: UUID,
    principal: Principal,
    profiles: Profiles,
) -> list[EnglishScenario]:
    _authorize_child(household_id, child_id, principal, profiles)
    return list(ENGLISH_SCENARIOS)


@router.post("/sessions", response_model=EnglishPracticeSession, status_code=201)
def start_session(
    household_id: UUID,
    child_id: UUID,
    body: StartEnglishSessionRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    request: Request,
    repository: Repository,
    profiles: Profiles,
) -> JSONResponse:
    _authorize_child(household_id, child_id, principal, profiles)
    if principal.role is not AccountRole.CHILD:
        raise HTTPException(status_code=403, detail="bound child principal required")
    try:
        session, replayed = repository.start_session(
            household_id,
            child_id,
            body.scenario_id,
            request.app.state.english_live_config,
            request.app.state.english_live_provider,
            idempotency_key,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail="scenario not found") from error
    except EnglishConsentRequiredError as error:
        raise HTTPException(
            status_code=409, detail="current guardian consent is required"
        ) from error
    except EnglishPracticeDisabledError as error:
        raise HTTPException(status_code=409, detail="english practice is unavailable") from error
    except EnglishActiveSessionError as error:
        raise HTTPException(status_code=409, detail="another english session is active") from error
    except EnglishSessionLimitError as error:
        raise HTTPException(
            status_code=429, detail="daily english practice limit reached"
        ) from error
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=409, detail="idempotency key reused with a different payload"
        ) from error
    _log_event("english_session_started", session)
    return JSONResponse(
        status_code=200 if replayed else 201,
        content=session.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


@router.get("/sessions", response_model=list[EnglishPracticeSession])
def list_sessions(
    household_id: UUID,
    child_id: UUID,
    principal: Principal,
    repository: Repository,
    profiles: Profiles,
    limit: int = Query(default=10, ge=1, le=10),
) -> tuple[EnglishPracticeSession, ...]:
    _authorize_child(household_id, child_id, principal, profiles)
    return repository.list_sessions(household_id, child_id, limit)


@router.post("/sessions/{session_id}/complete", response_model=EnglishPracticeSession)
def complete_session(
    household_id: UUID,
    child_id: UUID,
    session_id: UUID,
    body: CompleteEnglishSessionRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
    profiles: Profiles,
) -> JSONResponse:
    _authorize_child(household_id, child_id, principal, profiles)
    if principal.role is not AccountRole.CHILD:
        raise HTTPException(status_code=403, detail="bound child principal required")
    if body.status not in {EnglishSessionStatus.COMPLETED, EnglishSessionStatus.INTERRUPTED}:
        raise HTTPException(status_code=422, detail="invalid completion status")
    try:
        session, replayed = repository.complete_session(
            household_id, child_id, session_id, body.status, idempotency_key
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail="resource not found") from error
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=409, detail="idempotency key reused with a different payload"
        ) from error
    except EnglishSessionFinalizedError as error:
        raise HTTPException(
            status_code=409, detail="english session is already finalized"
        ) from error
    _log_event("english_session_completed", session)
    return JSONResponse(
        content=session.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


@router.websocket("/sessions/{session_id}/stream")
async def session_stream(
    websocket: WebSocket,
    household_id: UUID,
    child_id: UUID,
    session_id: UUID,
) -> None:
    token = _bearer_token(websocket.headers.get("authorization"))
    principal = _websocket_principal(websocket, token)
    if principal is None or principal.household_id != household_id:
        await websocket.close(code=4401)
        return
    if principal.role is not AccountRole.CHILD or principal.child_id != child_id:
        await websocket.close(code=4403)
        return
    profiles: ProfileRepository = websocket.app.state.profile_repository
    if profiles.get_child(household_id, child_id) is None:
        await websocket.close(code=4404)
        return
    repository: EnglishPracticeRepository = websocket.app.state.english_practice_repository
    session = repository.get_session(household_id, child_id, session_id)
    if session is None or session.status is not EnglishSessionStatus.ACTIVE:
        await websocket.close(code=4404)
        return
    provider: EnglishLiveProvider = websocket.app.state.english_live_provider
    config: EnglishLiveConfig = websocket.app.state.english_live_config
    if not provider.available or not config.provider_available:
        await websocket.close(code=4403)
        return

    live_session: EnglishLiveSession | None = None
    receive_task: asyncio.Task[Any] | None = None
    response_task: asyncio.Task[Any] | None = None
    await websocket.accept()
    try:
        live_session = await provider.open_session(
            scenario_id=session.scenario_id,
            level=session.level,
            policy_instruction=EnglishConversationPolicy().instruction(
                session.scenario_id, session.level
            ),
        )
        await websocket.send_json(_event("ready", session_id))
        while True:
            if _websocket_principal(websocket, token) is None:
                await websocket.send_json(_event("error", session_id, code="session_revoked"))
                await websocket.close(code=4401)
                return
            if (datetime.now(UTC) - session.started_at).total_seconds() >= (
                config.session_limit_seconds
            ):
                await websocket.send_json(_event("completed", session_id, reason="session_limit"))
                repository.complete_session(
                    household_id,
                    child_id,
                    session_id,
                    EnglishSessionStatus.COMPLETED,
                    f"ws-wall-limit-{session_id}",
                )
                return
            if receive_task is None:
                receive_task = asyncio.create_task(websocket.receive())
            wait_set: set[asyncio.Task[Any]] = {receive_task}
            if response_task is not None:
                wait_set.add(response_task)
            done, _ = await asyncio.wait(
                wait_set,
                return_when=asyncio.FIRST_COMPLETED,
                timeout=1 if response_task is not None else config.idle_timeout_seconds,
            )
            if not done:
                if response_task is not None:
                    continue
                await _cancel_task(receive_task)
                receive_task = None
                await websocket.send_json(_event("completed", session_id, reason="idle_timeout"))
                repository.complete_session(
                    household_id,
                    child_id,
                    session_id,
                    EnglishSessionStatus.INTERRUPTED,
                    f"ws-idle-{session_id}",
                    failure_code="idle_timeout",
                )
                return
            if response_task is not None and response_task in done:
                await response_task
                response_task = None
                continue
            assert receive_task is not None
            message = await receive_task
            receive_task = None
            if message.get("type") == "websocket.disconnect":
                raise WebSocketDisconnect
            data = message.get("bytes")
            if data is not None:
                if len(data) not in {640, 1280}:
                    await websocket.send_json(
                        _event("error", session_id, code="invalid_audio_frame")
                    )
                    await websocket.close(code=4400)
                    return
                if response_task is not None:
                    await _cancel_task(response_task)
                    response_task = None
                    await live_session.interrupt()
                input_ms = len(data) * 1000 // (2 * 16000)
                await live_session.send_audio(data)
                repository.record_audio(session_id, input_ms=input_ms)
                current = repository.get_session(household_id, child_id, session_id)
                if current is None or current.input_audio_ms > config.session_limit_seconds * 1000:
                    await websocket.send_json(
                        _event("completed", session_id, reason="session_limit")
                    )
                    repository.complete_session(
                        household_id,
                        child_id,
                        session_id,
                        EnglishSessionStatus.COMPLETED,
                        f"ws-limit-{session_id}",
                    )
                    return
                continue
            text = message.get("text")
            if text is None:
                continue
            try:
                event = json.loads(text)
            except json.JSONDecodeError:
                await websocket.send_json(_event("error", session_id, code="invalid_control"))
                continue
            event_type = (
                event.get("type")
                if isinstance(event, dict)
                and event.get("schema_version") == "english-live-client-event.v1"
                else None
            )
            if event_type == "listening":
                await websocket.send_json(_event("listening", session_id))
            elif event_type == "interrupt":
                if response_task is not None:
                    await _cancel_task(response_task)
                    response_task = None
                await live_session.interrupt()
                await websocket.send_json(_event("interrupted", session_id))
            elif event_type == "audio_stream_end":
                if response_task is not None:
                    await websocket.send_json(_event("error", session_id, code="turn_in_progress"))
                    continue
                repository.record_turn(session_id)
                await websocket.send_json(_event("thinking", session_id))
                await websocket.send_json(_event("speaking", session_id))
                response_task = asyncio.create_task(
                    _relay_provider_audio(
                        websocket,
                        live_session,
                        repository,
                        household_id,
                        child_id,
                        session_id,
                        config,
                    )
                )
            elif event_type == "complete":
                if response_task is not None:
                    await _cancel_task(response_task)
                    response_task = None
                completed, _ = repository.complete_session(
                    household_id,
                    child_id,
                    session_id,
                    EnglishSessionStatus.COMPLETED,
                    f"ws-complete-{session_id}",
                )
                await websocket.send_json(_event("completed", session_id))
                _log_event("english_session_completed", completed)
                return
            else:
                await websocket.send_json(_event("error", session_id, code="invalid_control"))
    except WebSocketDisconnect:
        current = repository.get_session(household_id, child_id, session_id)
        if current is not None and current.status is EnglishSessionStatus.ACTIVE:
            repository.complete_session(
                household_id,
                child_id,
                session_id,
                EnglishSessionStatus.INTERRUPTED,
                f"ws-disconnect-{session_id}",
                failure_code="connection_closed",
            )
    except Exception:  # noqa: BLE001 -- provider details must not cross the boundary.
        current = repository.get_session(household_id, child_id, session_id)
        if current is not None and current.status is EnglishSessionStatus.ACTIVE:
            repository.complete_session(
                household_id,
                child_id,
                session_id,
                EnglishSessionStatus.FAILED,
                f"ws-provider-error-{session_id}",
                failure_code="provider_stream_failed",
            )
        with suppress(Exception):
            await websocket.send_json(_event("error", session_id, code="provider_unavailable"))
            await websocket.close(code=1011)
    finally:
        await _cancel_task(response_task)
        await _cancel_task(receive_task)
        if live_session is not None:
            with suppress(Exception):
                await live_session.close()
        current = repository.get_session(household_id, child_id, session_id)
        if current is not None and current.status is EnglishSessionStatus.ACTIVE:
            repository.complete_session(
                household_id,
                child_id,
                session_id,
                EnglishSessionStatus.INTERRUPTED,
                f"ws-finalize-{session_id}",
                failure_code="connection_closed",
            )


async def _relay_provider_audio(
    websocket: WebSocket,
    live_session: EnglishLiveSession,
    repository: EnglishPracticeRepository,
    household_id: UUID,
    child_id: UUID,
    session_id: UUID,
    config: EnglishLiveConfig,
) -> None:
    async for audio in live_session.finish_input():
        if len(audio) not in {960, 1920}:
            raise ValueError("provider returned an invalid PCM frame")
        repository.record_audio(session_id, output_ms=len(audio) * 1000 // (2 * 24000))
        current = repository.get_session(household_id, child_id, session_id)
        if current is None or current.output_audio_ms > config.session_limit_seconds * 1000:
            raise ValueError("provider exceeded the session audio limit")
        await websocket.send_bytes(audio)


async def _cancel_task(task: asyncio.Task[Any] | None) -> None:
    if task is None or task.done():
        return
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


def _websocket_principal(websocket: WebSocket, token: str | None) -> AuthenticatedPrincipal | None:
    if token is None:
        return None
    try:
        account, session = websocket.app.state.auth_service.authenticate(token)
    except Exception:  # noqa: BLE001 -- keep session failures indistinguishable.
        return None
    if account.must_change_password:
        return None
    return AuthenticatedPrincipal(
        household_id=account.household_id,
        role=account.role,
        child_id=account.child_id,
        account_id=account.id,
        session_id=session.id,
    )


def _event(event_type: str, session_id: UUID, **fields: str) -> dict[str, str]:
    return {
        "schema_version": "english-live-server-event.v1",
        "type": event_type,
        "session_id": str(session_id),
        "event_id": str(uuid4()),
        **fields,
    }


def _log_event(event_name: str, session: EnglishPracticeSession) -> None:
    logger.info(
        event_name,
        extra={
            "event_name": event_name,
            "provider": session.provider,
            "model_version": session.model_version,
            "policy_version": session.policy_version,
            "result_status": session.status.value,
            "input_audio_ms": session.input_audio_ms,
            "output_audio_ms": session.output_audio_ms,
            "cost_micros": session.cost_micros,
        },
    )
