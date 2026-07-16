"""P0 API entrypoint for synthetic local/CI learning vertical slices."""

import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from study_api import __version__
from study_api.auth_domain import (
    AccountRepository,
    AuthService,
    InMemoryAccountRepository,
    PostgresAccountRepository,
)
from study_api.domain.capture_repository import CaptureRepository, InMemoryCaptureRepository
from study_api.domain.learning_repository import InMemoryLearningRepository
from study_api.domain.ocr_result_repository import (
    InMemoryOcrResultRepository,
    OcrResultRepository,
    PostgresOcrResultRepository,
)
from study_api.domain.question_extraction_repository import (
    InMemoryQuestionExtractionRepository,
    PostgresQuestionExtractionRepository,
    QuestionExtractionRepository,
)
from study_api.domain.repository import InMemoryProfileRepository
from study_api.domain.sql_capture_repository import PostgresCaptureRepository
from study_api.domain.sql_learning_repository import LearningRepository, PostgresLearningRepository
from study_api.domain.verified_question_repository import (
    InMemoryVerifiedQuestionRepository,
    PostgresVerifiedQuestionRepository,
    VerifiedQuestionRepository,
)
from study_api.image_analysis_jobs import (
    ImageAnalysisJobRepository,
    InMemoryImageAnalysisJobRepository,
    PostgresImageAnalysisJobRepository,
)
from study_api.newapi_provider import NewApiConfig
from study_api.object_storage import (
    CaptureObjectStorage,
    ObjectStorageConfig,
    ObjectStorageError,
    S3ObjectStorage,
    UnavailableObjectStorage,
)
from study_api.ocr_jobs import InMemoryOcrJobQueue, OcrJobQueue, PostgresOcrJobQueue
from study_api.routes.authentication import router as authentication_router
from study_api.routes.captures import router as capture_router
from study_api.routes.image_analysis import router as image_analysis_router
from study_api.routes.learning import router as learning_router
from study_api.routes.profiles import router as profile_router
from study_api.routes.tutor import router as tutor_router


def create_app(
    repository: InMemoryProfileRepository | None = None,
    learning_repository: LearningRepository | None = None,
    capture_repository: CaptureRepository | None = None,
    object_storage: CaptureObjectStorage | None = None,
    ocr_job_queue: OcrJobQueue | None = None,
    ocr_result_repository: OcrResultRepository | None = None,
    image_analysis_repository: ImageAnalysisJobRepository | None = None,
    question_extraction_repository: QuestionExtractionRepository | None = None,
    verified_question_repository: VerifiedQuestionRepository | None = None,
    account_repository: AccountRepository | None = None,
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
    app.state.ocr_job_queue = ocr_job_queue or _default_ocr_job_queue()
    app.state.ocr_result_repository = ocr_result_repository or _default_ocr_result_repository()
    app.state.image_analysis_repository = (
        image_analysis_repository or _default_image_analysis_repository()
    )
    app.state.question_extraction_repository = (
        question_extraction_repository or _default_question_extraction_repository()
    )
    app.state.verified_question_repository = (
        verified_question_repository or _default_verified_question_repository()
    )
    app.state.newapi_config = NewApiConfig.from_environment()
    app.state.account_repository = account_repository or _default_account_repository()
    app.state.auth_service = AuthService(app.state.account_repository)
    app.include_router(profile_router)
    app.include_router(authentication_router)
    app.include_router(learning_router)
    app.include_router(capture_router)
    app.include_router(image_analysis_router)
    app.include_router(tutor_router)

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


def _default_ocr_job_queue() -> OcrJobQueue:
    if os.environ.get("STUDY_API_OCR_QUEUE") == "postgres":
        return PostgresOcrJobQueue()
    return InMemoryOcrJobQueue()


def _default_ocr_result_repository() -> OcrResultRepository:
    if os.environ.get("STUDY_API_OCR_RESULTS") == "postgres":
        return PostgresOcrResultRepository()
    return InMemoryOcrResultRepository()


def _default_image_analysis_repository() -> ImageAnalysisJobRepository:
    if os.environ.get("STUDY_API_IMAGE_ANALYSIS_REPOSITORY") == "postgres":
        return PostgresImageAnalysisJobRepository()
    return InMemoryImageAnalysisJobRepository()


def _default_question_extraction_repository() -> QuestionExtractionRepository:
    if os.environ.get("STUDY_API_IMAGE_ANALYSIS_REPOSITORY") == "postgres":
        return PostgresQuestionExtractionRepository()
    return InMemoryQuestionExtractionRepository()


def _default_verified_question_repository() -> VerifiedQuestionRepository:
    if os.environ.get("STUDY_API_IMAGE_ANALYSIS_REPOSITORY") == "postgres":
        return PostgresVerifiedQuestionRepository()
    return InMemoryVerifiedQuestionRepository()


def _default_account_repository() -> AccountRepository:
    if os.environ.get("STUDY_API_AUTH_REPOSITORY") == "postgres":
        repository = PostgresAccountRepository()
        repository.ensure_bootstrap()
        return repository
    return InMemoryAccountRepository()


app = create_app()
