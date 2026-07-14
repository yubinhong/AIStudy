"""P0 API entrypoint for synthetic local/CI learning vertical slices."""

import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from study_api import __version__
from study_api.domain.capture_repository import CaptureRepository, InMemoryCaptureRepository
from study_api.domain.learning_repository import InMemoryLearningRepository
from study_api.domain.repository import InMemoryProfileRepository
from study_api.domain.sql_capture_repository import PostgresCaptureRepository
from study_api.domain.sql_learning_repository import LearningRepository, PostgresLearningRepository
from study_api.object_storage import (
    CaptureObjectStorage,
    ObjectStorageConfig,
    ObjectStorageError,
    S3ObjectStorage,
    UnavailableObjectStorage,
)
from study_api.routes.captures import router as capture_router
from study_api.routes.learning import router as learning_router
from study_api.routes.profiles import router as profile_router


def create_app(
    repository: InMemoryProfileRepository | None = None,
    learning_repository: LearningRepository | None = None,
    capture_repository: CaptureRepository | None = None,
    object_storage: CaptureObjectStorage | None = None,
) -> FastAPI:
    app = FastAPI(
        title="家庭 AI 学习助手 API",
        version=__version__,
        description="Synthetic local/CI household and learning contract vertical slices.",
    )
    app.state.profile_repository = repository or InMemoryProfileRepository()
    app.state.learning_repository = learning_repository or _default_learning_repository(
        app.state.profile_repository
    )
    app.state.capture_repository = capture_repository or _default_capture_repository(
        app.state.learning_repository
    )
    app.state.object_storage = object_storage or _default_object_storage()
    app.include_router(profile_router)
    app.include_router(learning_router)
    app.include_router(capture_router)

    @app.exception_handler(HTTPException)
    async def http_error_handler(_: Request, exception: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exception.status_code,
            content={
                "code": f"HTTP_{exception.status_code}",
                "message": str(exception.detail),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, __: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"code": "INVALID_REQUEST", "message": "request validation failed"},
        )

    @app.get("/healthz", tags=["system"])
    def health() -> dict[str, str]:
        """Return a non-sensitive readiness response."""

        return {"status": "ok", "service": "study-api", "version": __version__}

    return app


def _default_learning_repository(profiles: InMemoryProfileRepository) -> LearningRepository:
    if os.environ.get("STUDY_API_LEARNING_REPOSITORY") == "postgres":
        return PostgresLearningRepository(profiles)
    return InMemoryLearningRepository(profiles)


def _default_capture_repository(learning_repository: LearningRepository) -> CaptureRepository:
    if isinstance(learning_repository, PostgresLearningRepository):
        return PostgresCaptureRepository()
    return InMemoryCaptureRepository(learning_repository)


def _default_object_storage() -> CaptureObjectStorage:
    try:
        return S3ObjectStorage(ObjectStorageConfig.from_environment())
    except ObjectStorageError:
        return UnavailableObjectStorage()


app = create_app()
