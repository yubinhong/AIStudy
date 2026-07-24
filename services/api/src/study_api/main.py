"""家庭 AI 学习助手模块化 API 入口。"""

import asyncio
import os
from uuid import UUID

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
from study_api.child_management import (
    ChildManagementRepository,
    InMemoryChildManagementRepository,
    PostgresChildManagementRepository,
)
from study_api.curriculum_analysis_jobs import (
    CurriculumKnowledgeRepository,
    InMemoryCurriculumKnowledgeRepository,
    PostgresCurriculumKnowledgeRepository,
)
from study_api.domain.capture_repository import CaptureRepository, InMemoryCaptureRepository
from study_api.domain.curriculum_repository import (
    CurriculumRepository,
    InMemoryCurriculumRepository,
    PostgresCurriculumRepository,
)
from study_api.domain.insights_repository import (
    EmptyInsightsRepository,
    InsightsRepository,
    PostgresInsightsRepository,
)
from study_api.domain.learning_repository import InMemoryLearningRepository
from study_api.domain.mistake_repository import (
    InMemoryMistakeRepository,
    MistakeRepository,
    PostgresMistakeRepository,
)
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
from study_api.domain.recommendation_repository import (
    InMemoryTaskRecommendationRepository,
    PostgresTaskRecommendationRepository,
    TaskRecommendationRepository,
)
from study_api.domain.repository import InMemoryProfileRepository, ProfileRepository
from study_api.domain.sql_capture_repository import PostgresCaptureRepository
from study_api.domain.sql_learning_repository import LearningRepository, PostgresLearningRepository
from study_api.domain.sql_profile_repository import PostgresProfileRepository
from study_api.domain.tutor_turn_repository import (
    InMemoryTutorTurnRepository,
    PostgresTutorTurnRepository,
    TutorTurnRepository,
)
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
from study_api.material_parse_jobs import MaterialParseRepository, PostgresMaterialParseRepository
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
from study_api.routes.curriculum import router as curriculum_router
from study_api.routes.image_analysis import router as image_analysis_router
from study_api.routes.insights import router as insights_router
from study_api.routes.learning import router as learning_router
from study_api.routes.mistakes import router as mistakes_router
from study_api.routes.profiles import router as profile_router
from study_api.routes.recommendations import router as recommendations_router
from study_api.routes.tutor import router as tutor_router


def create_app(
    repository: ProfileRepository | None = None,
    learning_repository: LearningRepository | None = None,
    capture_repository: CaptureRepository | None = None,
    object_storage: CaptureObjectStorage | None = None,
    ocr_job_queue: OcrJobQueue | None = None,
    ocr_result_repository: OcrResultRepository | None = None,
    image_analysis_repository: ImageAnalysisJobRepository | None = None,
    question_extraction_repository: QuestionExtractionRepository | None = None,
    verified_question_repository: VerifiedQuestionRepository | None = None,
    tutor_turn_repository: TutorTurnRepository | None = None,
    insights_repository: InsightsRepository | None = None,
    mistake_repository: MistakeRepository | None = None,
    account_repository: AccountRepository | None = None,
    curriculum_repository: CurriculumRepository | None = None,
    recommendation_repository: TaskRecommendationRepository | None = None,
    material_parse_repository: MaterialParseRepository | None = None,
    curriculum_knowledge_repository: CurriculumKnowledgeRepository | None = None,
) -> FastAPI:
    app = FastAPI(
        title="家庭 AI 学习助手 API",
        version=__version__,
        description="Household-scoped learning, capture, profile, and authentication API.",
    )
    app.state.profile_repository = repository or _default_profile_repository()
    app.state.learning_repository = learning_repository or _default_learning_repository(
        app.state.profile_repository
    )
    app.state.capture_repository = capture_repository or _default_capture_repository(
        app.state.learning_repository
    )
    app.state.object_storage = object_storage or _default_object_storage()
    app.state.capture_upload_semaphore = asyncio.Semaphore(_capture_upload_concurrency())
    app.state.capture_upload_timeout_seconds = _capture_upload_timeout_seconds()
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
    app.state.tutor_turn_repository = tutor_turn_repository or _default_tutor_turn_repository()
    app.state.insights_repository = insights_repository or _default_insights_repository()
    app.state.mistake_repository = mistake_repository or _default_mistake_repository()
    app.state.newapi_config = NewApiConfig.from_environment()
    app.state.account_repository = account_repository or _default_account_repository()
    app.state.curriculum_repository = curriculum_repository or _default_curriculum_repository()
    app.state.recommendation_repository = (
        recommendation_repository or _default_recommendation_repository()
    )
    app.state.material_parse_repository = (
        material_parse_repository or _default_material_parse_repository()
    )
    app.state.curriculum_knowledge_repository = (
        curriculum_knowledge_repository or _default_curriculum_knowledge_repository()
    )
    app.state.auth_service = AuthService(app.state.account_repository)
    app.state.child_management_repository = _default_child_management_repository(
        app.state.profile_repository,
        app.state.account_repository,
        app.state.auth_service,
    )
    app.include_router(profile_router)
    app.include_router(authentication_router)
    app.include_router(learning_router)
    app.include_router(capture_router)
    app.include_router(image_analysis_router)
    app.include_router(tutor_router)
    app.include_router(insights_router)
    app.include_router(mistakes_router)
    app.include_router(curriculum_router)
    app.include_router(recommendations_router)

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


def _default_profile_repository() -> ProfileRepository:
    if os.environ.get("STUDY_API_PROFILE_REPOSITORY") == "postgres":
        return PostgresProfileRepository()
    return InMemoryProfileRepository()


def _default_child_management_repository(
    profiles: ProfileRepository,
    accounts: AccountRepository,
    auth_service: AuthService,
) -> ChildManagementRepository:
    if isinstance(profiles, PostgresProfileRepository) and isinstance(
        accounts, PostgresAccountRepository
    ):
        return PostgresChildManagementRepository(engine=profiles.engine)
    return InMemoryChildManagementRepository(profiles, accounts, auth_service)


def _capture_upload_concurrency() -> int:
    try:
        value = int(os.environ.get("STUDY_CAPTURE_UPLOAD_CONCURRENCY", "4"))
    except ValueError as error:
        raise RuntimeError("STUDY_CAPTURE_UPLOAD_CONCURRENCY must be an integer") from error
    if not 1 <= value <= 32:
        raise RuntimeError("STUDY_CAPTURE_UPLOAD_CONCURRENCY must be between 1 and 32")
    return value


def _capture_upload_timeout_seconds() -> float:
    try:
        value = float(os.environ.get("STUDY_CAPTURE_UPLOAD_TIMEOUT_SECONDS", "120"))
    except ValueError as error:
        raise RuntimeError("STUDY_CAPTURE_UPLOAD_TIMEOUT_SECONDS must be a number") from error
    if not 5 <= value <= 600:
        raise RuntimeError("STUDY_CAPTURE_UPLOAD_TIMEOUT_SECONDS must be between 5 and 600")
    return value


def _default_learning_repository(profiles: ProfileRepository) -> LearningRepository:
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


def _default_tutor_turn_repository() -> TutorTurnRepository:
    if os.environ.get("STUDY_API_IMAGE_ANALYSIS_REPOSITORY") == "postgres":
        return PostgresTutorTurnRepository()
    return InMemoryTutorTurnRepository()


def _default_insights_repository() -> InsightsRepository:
    if os.environ.get("STUDY_API_LEARNING_REPOSITORY") == "postgres":
        return PostgresInsightsRepository()
    return EmptyInsightsRepository()


def _default_mistake_repository() -> MistakeRepository:
    if os.environ.get("STUDY_API_LEARNING_REPOSITORY") == "postgres":
        return PostgresMistakeRepository()
    return InMemoryMistakeRepository()


def _default_curriculum_repository() -> CurriculumRepository:
    if (
        os.environ.get("STUDY_API_CURRICULUM_REPOSITORY") == "postgres"
        or os.environ.get("STUDY_API_LEARNING_REPOSITORY") == "postgres"
    ):
        return PostgresCurriculumRepository()
    return InMemoryCurriculumRepository()


def _default_recommendation_repository() -> TaskRecommendationRepository:
    if os.environ.get("STUDY_API_LEARNING_REPOSITORY") == "postgres":
        return PostgresTaskRecommendationRepository()
    return InMemoryTaskRecommendationRepository()


def _default_material_parse_repository() -> MaterialParseRepository:
    if os.environ.get("STUDY_API_LEARNING_REPOSITORY") == "postgres":
        return PostgresMaterialParseRepository()
    return _NoopMaterialParseRepository()


def _default_curriculum_knowledge_repository() -> CurriculumKnowledgeRepository:
    if os.environ.get("STUDY_API_LEARNING_REPOSITORY") == "postgres":
        return PostgresCurriculumKnowledgeRepository()
    return InMemoryCurriculumKnowledgeRepository()


class _NoopMaterialParseRepository:
    def enqueue(
        self,
        household_id: UUID,
        child_id: UUID,
        material_id: UUID,
        snapshot_id: UUID,
    ) -> None:  # pragma: no cover - manifest-only in-memory test path
        del household_id, child_id, material_id, snapshot_id

    def close(self) -> None:
        return None


def _default_account_repository() -> AccountRepository:
    if os.environ.get("STUDY_API_AUTH_REPOSITORY") == "postgres":
        repository = PostgresAccountRepository()
        repository.ensure_bootstrap()
        return repository
    return InMemoryAccountRepository()


app = create_app()
