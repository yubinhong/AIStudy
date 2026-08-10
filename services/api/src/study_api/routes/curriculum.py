"""Parent-reviewed curriculum import and publication routes."""

from hashlib import sha256
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi import (
    Path as ApiPath,
)
from fastapi.responses import JSONResponse, Response

from study_api.auth import (
    AuthenticatedPrincipal,
    get_principal,
    require_household,
    require_parent,
)
from study_api.curriculum_analysis_jobs import CurriculumKnowledgeRepository
from study_api.curriculum_limits import MAX_DOCUMENT_BYTES, MAX_TOTAL_DOCUMENT_BYTES
from study_api.domain.curriculum_knowledge import CurriculumKnowledgeMap, KnowledgeMapStatus
from study_api.domain.curriculum_repository import (
    CurriculumImportResult,
    CurriculumParsedPage,
    CurriculumRepository,
    CurriculumSection,
    CurriculumSnapshot,
    ImportCurriculumRequest,
)
from study_api.domain.models import AccountRole
from study_api.domain.repository import IdempotencyConflictError
from study_api.material_parser import provisional_textbook_title
from study_api.object_storage import CaptureObjectStorage, ObjectStorageError

router = APIRouter(prefix="/households/{household_id}", tags=["curriculum"])
Principal = Annotated[AuthenticatedPrincipal, Depends(get_principal)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]
DOCUMENT_MEDIA_TYPES = {
    ".pdf": "application/pdf",
}


def get_repository(request: Request) -> CurriculumRepository:
    return request.app.state.curriculum_repository


Repository = Annotated[CurriculumRepository, Depends(get_repository)]


def get_object_storage(request: Request) -> CaptureObjectStorage:
    return request.app.state.object_storage


ObjectStorage = Annotated[CaptureObjectStorage, Depends(get_object_storage)]


def get_knowledge_repository(request: Request) -> CurriculumKnowledgeRepository:
    return request.app.state.curriculum_knowledge_repository


KnowledgeRepository = Annotated[CurriculumKnowledgeRepository, Depends(get_knowledge_repository)]


def _require_child(
    principal: AuthenticatedPrincipal, request: Request, household_id: UUID, child_id: UUID
) -> None:
    child = request.app.state.profile_repository.get_child(household_id, child_id)
    if (
        child is None
        or (principal.role is AccountRole.CHILD and principal.child_id != child_id)
        or (
            principal.role is not AccountRole.CHILD
            and child.owner_account_id != principal.account_id
        )
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")


@router.post(
    "/children/{child_id}/curriculum/imports",
    response_model=CurriculumImportResult,
    status_code=status.HTTP_201_CREATED,
)
def import_curriculum(
    household_id: UUID,
    child_id: UUID,
    request: ImportCurriculumRequest,
    app_request: Request,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
) -> JSONResponse:
    require_parent(require_household(principal, household_id))
    _require_child(principal, app_request, household_id, child_id)
    try:
        result, replayed = repository.import_draft(household_id, child_id, request, idempotency_key)
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency key reused with a different payload",
        ) from error
    return JSONResponse(
        status_code=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        content=result.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


async def _upload_size_and_hash(upload: UploadFile) -> tuple[int, str]:
    total = 0
    digest = sha256()
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_DOCUMENT_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="curriculum document is too large",
            )
        digest.update(chunk)
    await upload.seek(0)
    if total == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="curriculum document is empty",
        )
    return total, digest.hexdigest()


async def _validate_pdf_header(upload: UploadFile) -> None:
    header = await upload.read(8)
    await upload.seek(0)
    if not header.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="invalid_pdf_document",
        )


async def _upload_chunks(upload: UploadFile):
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        yield chunk


@router.post(
    "/children/{child_id}/curriculum/imports/files",
    response_model=list[CurriculumImportResult],
    status_code=status.HTTP_201_CREATED,
)
async def import_curriculum_files(
    household_id: UUID,
    child_id: UUID,
    app_request: Request,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
    object_storage: ObjectStorage,
    knowledge_repository: KnowledgeRepository,
    files: Annotated[list[UploadFile], File(min_length=1)],
    grade: Annotated[int, Form(ge=1, le=6)],
    authorization_statement: Annotated[str, Form(min_length=1, max_length=500)],
    is_public_reusable: Annotated[bool, Form()] = False,
    textbook_version: Annotated[str | None, Form(min_length=1, max_length=120)] = None,
    term: Annotated[str | None, Form(min_length=1, max_length=40)] = None,
) -> list[CurriculumImportResult]:
    """Upload files or reuse a parent-declared public textbook by exact hash."""

    require_parent(require_household(principal, household_id))
    _require_child(principal, app_request, household_id, child_id)
    if not files:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="files required",
        )

    total_bytes = 0
    prepared: list[tuple[UploadFile, str, str, int, str]] = []
    # Validate the entire batch before writing the first object. A mixed PDF/
    # DOCX request must fail atomically at the upload boundary.
    for upload in files:
        filename = Path(upload.filename or "").name
        suffix = Path(filename).suffix.lower()
        media_type = DOCUMENT_MEDIA_TYPES.get(suffix)
        if media_type is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="unsupported_material_format",
            )
        await _validate_pdf_header(upload)
        byte_size, content_sha256 = await _upload_size_and_hash(upload)
        total_bytes += byte_size
        if total_bytes > MAX_TOTAL_DOCUMENT_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="curriculum upload batch is too large",
            )
        prepared.append((upload, filename, media_type, byte_size, content_sha256))

    results: list[CurriculumImportResult] = []
    for upload, filename, media_type, byte_size, content_sha256 in prepared:
        suffix = Path(filename).suffix.lower()
        safe_name = filename[:160] or f"document{suffix}"
        section_title = Path(safe_name).stem[:160] or "待解析文档"
        import_request = ImportCurriculumRequest(
            filename=safe_name,
            media_type=media_type,
            byte_size=byte_size,
            content_sha256=content_sha256,
            authorization_statement=authorization_statement,
            is_public_reusable=is_public_reusable,
            grade=grade,
            textbook_version=textbook_version or provisional_textbook_title(safe_name),
            term=term or "待识别",
            sections=(
                CurriculumSection(
                    title=section_title,
                    chapter="待解析文档",
                    learning_objectives=("等待文档解析和家长审核",),
                ),
            ),
        )
        name_hash = sha256(safe_name.encode("utf-8")).hexdigest()[:16]
        object_key = f"curriculum/{household_id}/{child_id}/{content_sha256}-{name_hash}"
        file_key = sha256(f"{idempotency_key}:{content_sha256}:{safe_name}".encode()).hexdigest()
        try:
            reusable_source = (
                repository.find_public_reusable_snapshot(import_request)
                if is_public_reusable
                else None
            )
            if reusable_source is not None:
                source_map = knowledge_repository.get_map(
                    reusable_source.snapshot.household_id,
                    reusable_source.snapshot.child_id,
                    reusable_source.snapshot.id,
                )
                if source_map is None or source_map.status is not KnowledgeMapStatus.APPROVED:
                    reusable_source = None
            if reusable_source is not None and reusable_source.material.object_key is not None:
                result, _ = repository.import_draft(
                    household_id,
                    child_id,
                    import_request,
                    file_key,
                    object_key=reusable_source.material.object_key,
                    reused_from_snapshot_id=reusable_source.snapshot.id,
                )
                repository.clone_parsed_content(reusable_source.snapshot.id, result)
                knowledge_repository.clone_approved_public_map(
                    reusable_source.snapshot.id,
                    result.material.id,
                    result.snapshot.id,
                    household_id,
                    child_id,
                )
                result = result.model_copy(
                    update={
                        "material": result.material.model_copy(update={"status": "needs_review"}),
                        "snapshot": result.snapshot.model_copy(
                            update={
                                "sections": reusable_source.snapshot.sections,
                                "textbook_version": reusable_source.snapshot.textbook_version,
                                "term": reusable_source.snapshot.term,
                            }
                        ),
                    }
                )
                results.append(result)
                continue
            await object_storage.stream_document_upload(
                object_key, media_type, byte_size, content_sha256, _upload_chunks(upload)
            )
            result, _ = repository.import_draft(
                household_id,
                child_id,
                import_request,
                file_key,
                object_key=object_key,
            )
            parse_repository = getattr(app_request.app.state, "material_parse_repository", None)
            if parse_repository is not None:
                parse_repository.enqueue(
                    household_id,
                    child_id,
                    result.material.id,
                    result.snapshot.id,
                )
        except ObjectStorageError as error:
            raise HTTPException(
                status_code=(
                    status.HTTP_503_SERVICE_UNAVAILABLE
                    if error.retryable
                    else status.HTTP_422_UNPROCESSABLE_CONTENT
                ),
                detail=str(error),
            ) from error
        except IdempotencyConflictError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="idempotency key reused with a different payload",
            ) from error
        results.append(result)
    return results


@router.get("/children/{child_id}/curriculum", response_model=list[CurriculumSnapshot])
def list_curriculum(
    household_id: UUID,
    child_id: UUID,
    principal: Principal,
    repository: Repository,
    app_request: Request,
) -> list[CurriculumSnapshot]:
    role = require_household(principal, household_id)
    _require_child(principal, app_request, household_id, child_id)
    published_only = role.value == "child"
    return repository.list_snapshots(household_id, child_id, published_only)


@router.get(
    "/children/{child_id}/curriculum/snapshots/{snapshot_id}/pages",
    response_model=list[CurriculumParsedPage],
)
def list_curriculum_snapshot_pages(
    household_id: UUID,
    child_id: UUID,
    snapshot_id: UUID,
    principal: Principal,
    repository: Repository,
    knowledge_repository: KnowledgeRepository,
    app_request: Request,
) -> list[CurriculumParsedPage]:
    """Return parent-only, page-scoped text for a readable review document."""

    require_parent(require_household(principal, household_id))
    _require_child(principal, app_request, household_id, child_id)
    if repository.get_material_for_snapshot(household_id, child_id, snapshot_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    pages: list[CurriculumParsedPage] = []
    for chunk in repository.list_review_chunks(household_id, child_id, snapshot_id):
        asset = knowledge_repository.get_page_asset(
            household_id, child_id, snapshot_id, chunk.page_number
        )
        pages.append(
            CurriculumParsedPage(
                page_number=chunk.page_number,
                title=chunk.title,
                text=chunk.text,
                confidence=chunk.confidence,
                image_available=asset is not None,
                image_path=(
                    f"/households/{household_id}/children/{child_id}/curriculum/"
                    f"snapshots/{snapshot_id}/pages/{chunk.page_number}/image"
                    if asset is not None
                    else None
                ),
            )
        )
    return pages


@router.get(
    "/children/{child_id}/curriculum/snapshots/{snapshot_id}/analysis",
    response_model=CurriculumKnowledgeMap,
)
def get_curriculum_analysis(
    household_id: UUID,
    child_id: UUID,
    snapshot_id: UUID,
    principal: Principal,
    repository: Repository,
    knowledge_repository: KnowledgeRepository,
    app_request: Request,
) -> CurriculumKnowledgeMap:
    role = require_household(principal, household_id)
    _require_child(principal, app_request, household_id, child_id)
    if role.value == "child" and principal.child_id != child_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    if repository.get_material_for_snapshot(household_id, child_id, snapshot_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    knowledge_map = knowledge_repository.get_map(household_id, child_id, snapshot_id)
    if knowledge_map is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="analysis not found")
    if role.value == "child" and knowledge_map.status is not KnowledgeMapStatus.APPROVED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    return knowledge_map


@router.post(
    "/children/{child_id}/curriculum/snapshots/{snapshot_id}/analysis",
    response_model=CurriculumKnowledgeMap,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_curriculum_analysis(
    household_id: UUID,
    child_id: UUID,
    snapshot_id: UUID,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
    knowledge_repository: KnowledgeRepository,
    app_request: Request,
) -> CurriculumKnowledgeMap:
    require_parent(require_household(principal, household_id))
    _require_child(principal, app_request, household_id, child_id)
    material = repository.get_material_for_snapshot(household_id, child_id, snapshot_id)
    if material is None or material.object_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    del idempotency_key
    try:
        return knowledge_repository.enqueue(household_id, child_id, material.id, snapshot_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.post(
    "/children/{child_id}/curriculum/snapshots/{snapshot_id}/analysis/approve",
    response_model=CurriculumKnowledgeMap,
)
def approve_curriculum_analysis(
    household_id: UUID,
    child_id: UUID,
    snapshot_id: UUID,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    knowledge_repository: KnowledgeRepository,
    app_request: Request,
) -> CurriculumKnowledgeMap:
    require_parent(require_household(principal, household_id))
    _require_child(principal, app_request, household_id, child_id)
    del idempotency_key
    try:
        return knowledge_repository.approve(household_id, child_id, snapshot_id)
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="analysis not found"
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.get(
    "/children/{child_id}/curriculum/snapshots/{snapshot_id}/pages/{page_number}/image",
    response_class=Response,
)
def get_curriculum_page_image(
    household_id: UUID,
    child_id: UUID,
    snapshot_id: UUID,
    page_number: Annotated[int, ApiPath(ge=1, le=400)],
    principal: Principal,
    repository: Repository,
    knowledge_repository: KnowledgeRepository,
    object_storage: ObjectStorage,
    app_request: Request,
) -> Response:
    role = require_household(principal, household_id)
    _require_child(principal, app_request, household_id, child_id)
    if role.value == "child":
        if principal.child_id != child_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
        published_ids = {
            snapshot.id
            for snapshot in repository.list_snapshots(household_id, child_id, published_only=True)
        }
        if snapshot_id not in published_ids:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    asset = knowledge_repository.get_page_asset(household_id, child_id, snapshot_id, page_number)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="page image not found")
    try:
        data = object_storage.read_curriculum_preview(asset.object_key)
    except ObjectStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="page image is temporarily unavailable",
        ) from error
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/children/{child_id}/curriculum/snapshots/{snapshot_id}/publish",
    response_model=CurriculumSnapshot,
)
def publish_curriculum(
    household_id: UUID,
    child_id: UUID,
    snapshot_id: UUID,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
    knowledge_repository: KnowledgeRepository,
    app_request: Request,
) -> JSONResponse:
    require_parent(require_household(principal, household_id))
    _require_child(principal, app_request, household_id, child_id)
    material = repository.get_material_for_snapshot(household_id, child_id, snapshot_id)
    if (
        material is not None
        and material.object_key is not None
        and material.status not in {"uploaded", "queued", "parsing"}
    ):
        knowledge_map = knowledge_repository.get_map(household_id, child_id, snapshot_id)
        if knowledge_map is None or knowledge_map.status is not KnowledgeMapStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="curriculum knowledge must be analyzed and approved before publication",
            )
    try:
        snapshot, replayed = repository.publish(
            household_id, child_id, snapshot_id, idempotency_key
        )
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="resource not found"
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency key reused with a different payload",
        ) from error
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=snapshot.model_dump(mode="json"),
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )


@router.delete(
    "/children/{child_id}/curriculum/snapshots/{snapshot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_curriculum_snapshot(
    household_id: UUID,
    child_id: UUID,
    snapshot_id: UUID,
    idempotency_key: IdempotencyKey,
    principal: Principal,
    repository: Repository,
    knowledge_repository: KnowledgeRepository,
    object_storage: ObjectStorage,
    app_request: Request,
) -> Response:
    """Delete one parent-owned material, its parsed chunks, and private source object."""

    require_parent(require_household(principal, household_id))
    _require_child(principal, app_request, household_id, child_id)
    existing_material = repository.get_material_for_snapshot(household_id, child_id, snapshot_id)
    assets_to_delete = [
        asset
        for asset in knowledge_repository.list_page_assets(household_id, child_id, snapshot_id)
        if not knowledge_repository.has_other_asset_reference(asset.object_key, snapshot_id)
    ]
    material_object_should_delete = bool(
        existing_material
        and existing_material.object_key
        and not repository.has_other_material_reference(
            existing_material.object_key, existing_material.id
        )
    )
    # Delete only objects whose final reference is this snapshot. References
    # are checked before the DB cascade so one family cannot delete a public
    # textbook or page image still used by another family.
    for asset in assets_to_delete:
        try:
            object_storage.delete_object(asset.object_key)
        except ObjectStorageError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="curriculum page images could not be deleted from private storage",
            ) from error
    if (
        material_object_should_delete
        and existing_material is not None
        and existing_material.object_key
    ):
        try:
            object_storage.delete_object(existing_material.object_key)
        except ObjectStorageError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="curriculum document could not be deleted from private storage",
            ) from error
    try:
        material, replayed = repository.delete_snapshot(
            household_id, child_id, snapshot_id, idempotency_key
        )
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="resource not found"
        ) from error
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency key reused with a different payload",
        ) from error
    del material
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
        headers={"Idempotency-Replayed": "true"} if replayed else {},
    )
