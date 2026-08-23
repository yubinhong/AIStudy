"""Task, StudySession, Attempt and offline sync routes for synthetic local/CI tests."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from study_api.auth import (
    AuthenticatedPrincipal,
    get_principal,
    require_bound_child,
    require_household,
    require_parent,
)
from study_api.domain.learning_repository import (
    ChildAssignmentError,
    ResourceVersionConflictError,
    SessionAlreadyCompletedError,
    SessionNotActiveError,
    TaskCapacityError,
    TaskNotRevocableError,
    TaskNotScheduledError,
    TaskNotStartableError,
    TaskProgressConflictError,
)
from study_api.domain.models import (
    AccountRole,
    Attempt,
    CompleteStudySessionRequest,
    CreateTaskRequest,
    RecordAttemptRequest,
    StartStudySessionRequest,
    StudySession,
    StudyTask,
    SyncBatchRequest,
    SyncBatchResult,
)
from study_api.domain.repository import IdempotencyConflictError
from study_api.domain.sql_learning_repository import LearningRepository

router = APIRouter(prefix="/households/{household_id}", tags=["learning"])
Principal = Annotated[AuthenticatedPrincipal, Depends(get_principal)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


def get_learning_repository(request: Request) -> LearningRepository:
    return request.app.state.learning_repository


Repository = Annotated[LearningRepository, Depends(get_learning_repository)]


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


@router.get("/tasks", response_model=list[StudyTask])
def list_tasks(
    household_id: UUID,
    principal: Principal,
    repository: Repository,
    child_id: Annotated[UUID | None, Query()] = None,
) -> list[StudyTask]:
    role = require_household(principal, household_id)
    if role is AccountRole.CHILD:
        bound_child_id = require_bound_child(principal)
        if child_id is not None and child_id != bound_child_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
        child_id = bound_child_id
    return repository.list_tasks(household_id, child_id)


@router.post("/tasks", response_model=StudyTask, status_code=status.HTTP_201_CREATED)
def create_task(
    household_id: UUID,
    request: CreateTaskRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
) -> JSONResponse:
    require_parent(require_household(principal, household_id))
    try:
        task, replayed = repository.create_task(household_id, request, idempotency_key)
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="resource not found"
        ) from error
    except IdempotencyConflictError as error:
        raise _conflict("idempotency key reused with a different payload") from error
    except TaskCapacityError as error:
        raise _conflict("daily task capacity reached") from error
    return JSONResponse(
        status_code=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        content=task.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


@router.post(
    "/tasks/{task_id}/sessions", response_model=StudySession, status_code=status.HTTP_201_CREATED
)
def start_session(
    household_id: UUID,
    task_id: UUID,
    request: StartStudySessionRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
) -> JSONResponse:
    require_household(principal, household_id)
    child_id = require_bound_child(principal)
    try:
        session, replayed = repository.start_session(
            household_id, task_id, child_id, request, idempotency_key
        )
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="resource not found"
        ) from error
    except ChildAssignmentError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="resource not found"
        ) from error
    except ResourceVersionConflictError as error:
        raise _conflict("task version conflict") from error
    except TaskNotStartableError as error:
        raise _conflict("task is no longer available to start") from error
    except TaskNotScheduledError as error:
        raise _conflict("task is not scheduled yet") from error
    except IdempotencyConflictError as error:
        raise _conflict("idempotency key reused with a different payload") from error
    return JSONResponse(
        status_code=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        content=session.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


@router.post("/tasks/{task_id}/revoke", response_model=StudyTask)
def revoke_task(
    household_id: UUID,
    task_id: UUID,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
) -> JSONResponse:
    """Revoke a parent-assigned task and close any active child session."""

    require_parent(require_household(principal, household_id))
    try:
        task, replayed = repository.revoke_task(household_id, task_id, idempotency_key)
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="resource not found"
        ) from error
    except TaskNotRevocableError as error:
        raise _conflict("task is no longer revocable") from error
    except IdempotencyConflictError as error:
        raise _conflict("idempotency key reused with a different payload") from error
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=task.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


@router.get("/tasks/{task_id}/active-session", response_model=StudySession)
def get_active_session(
    household_id: UUID,
    task_id: UUID,
    principal: Principal,
    repository: Repository,
) -> StudySession:
    require_household(principal, household_id)
    child_id = require_bound_child(principal)
    session = repository.find_active_session(household_id, task_id, child_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    return session


@router.post("/capture-sessions", response_model=StudySession, status_code=status.HTTP_201_CREATED)
def create_capture_session(
    household_id: UUID,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
) -> JSONResponse:
    """Create or replay a bound child's ad-hoc session for photo questions."""

    require_household(principal, household_id)
    child_id = require_bound_child(principal)
    try:
        session, replayed = repository.create_capture_session(
            household_id, child_id, idempotency_key
        )
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="resource not found"
        ) from error
    except IdempotencyConflictError as error:
        raise _conflict("idempotency key reused with a different payload") from error
    return JSONResponse(
        status_code=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        content=session.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


@router.post(
    "/sessions/{session_id}/attempts", response_model=Attempt, status_code=status.HTTP_201_CREATED
)
def record_attempt(
    household_id: UUID,
    session_id: UUID,
    request: RecordAttemptRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
) -> JSONResponse:
    require_household(principal, household_id)
    child_id = require_bound_child(principal)
    try:
        attempt, replayed = repository.record_attempt(
            household_id, session_id, child_id, request, idempotency_key
        )
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="resource not found"
        ) from error
    except ChildAssignmentError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="resource not found"
        ) from error
    except SessionNotActiveError as error:
        raise _conflict("study session is no longer active") from error
    except TaskProgressConflictError as error:
        raise _conflict("task exercise progress conflict") from error
    except IdempotencyConflictError as error:
        raise _conflict("idempotency key reused with a different payload") from error
    return JSONResponse(
        status_code=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        content=attempt.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


@router.post("/sessions/{session_id}/completion", response_model=StudySession)
def complete_session(
    household_id: UUID,
    session_id: UUID,
    request: CompleteStudySessionRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
) -> JSONResponse:
    require_household(principal, household_id)
    child_id = require_bound_child(principal)
    try:
        session, replayed = repository.complete_session(
            household_id, session_id, child_id, request, idempotency_key
        )
    except (LookupError, ChildAssignmentError) as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="resource not found"
        ) from error
    except SessionAlreadyCompletedError as error:
        raise _conflict("study session is already completed") from error
    except SessionNotActiveError as error:
        raise _conflict("study session is no longer active") from error
    except IdempotencyConflictError as error:
        raise _conflict("idempotency key reused with a different payload") from error
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=session.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


@router.post("/sync-batches", response_model=SyncBatchResult)
def sync_batch(
    household_id: UUID,
    request: SyncBatchRequest,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
) -> SyncBatchResult:
    del (
        idempotency_key
    )  # Each event has its own idempotency key; header remains a write-boundary requirement.
    require_household(principal, household_id)
    child_id = require_bound_child(principal)
    try:
        return repository.sync_attempts(household_id, child_id, request)
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="resource not found"
        ) from error
    except ChildAssignmentError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="resource not found"
        ) from error
    except SessionNotActiveError as error:
        raise _conflict("study session is no longer active") from error
    except TaskProgressConflictError as error:
        raise _conflict("task exercise progress conflict") from error
    except IdempotencyConflictError as error:
        raise _conflict("offline event conflict") from error
