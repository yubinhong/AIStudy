from collections.abc import AsyncIterable
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

import pytest
from auth_helpers import session_headers
from fastapi.testclient import TestClient

from study_api.chinese_practice import ChinesePoemDraft, InMemoryChinesePracticeRepository
from study_api.curriculum_analysis_jobs import InMemoryCurriculumKnowledgeRepository
from study_api.curriculum_limits import MAX_DOCUMENT_BYTES
from study_api.domain.curriculum_knowledge import (
    CurriculumKnowledgeExercise,
    CurriculumKnowledgeMap,
    CurriculumKnowledgePoint,
    KnowledgeMapStatus,
)
from study_api.domain.curriculum_repository import (
    CurriculumChunk,
    InMemoryCurriculumRepository,
)
from study_api.main import create_app
from study_api.newapi_provider import NewApiConfig, NewApiVisionProvider
from study_api.recommendation_engine import (
    ProviderRecommendationItem,
    ProviderRecommendationPlan,
)

HOUSEHOLD_A = "00000000-0000-0000-0000-000000000001"
CHILD_A = "00000000-0000-0000-0000-000000000101"


class MemoryDocumentStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def stream_document_upload(
        self,
        object_key: str,
        content_type: str,
        byte_size: int,
        content_sha256: str,
        chunks: AsyncIterable[bytes],
    ) -> None:
        del content_type
        data = b"".join([chunk async for chunk in chunks])
        assert len(data) == byte_size
        assert sha256(data).hexdigest() == content_sha256
        self.objects[object_key] = data

    def delete_object(self, object_key: str) -> None:
        self.objects.pop(object_key, None)


class CurriculumWithChunks(InMemoryCurriculumRepository):
    def __init__(self) -> None:
        super().__init__()
        self.chunks: list[CurriculumChunk] = []

    def list_chunks(
        self,
        household_id: UUID,
        child_id: UUID,
        snapshot_id: UUID,
    ) -> list[CurriculumChunk]:
        return [
            chunk
            for chunk in self.chunks
            if chunk.household_id == household_id
            and chunk.child_id == child_id
            and chunk.snapshot_id == snapshot_id
        ]

    def list_review_chunks(
        self,
        household_id: UUID,
        child_id: UUID,
        snapshot_id: UUID,
    ) -> list[CurriculumChunk]:
        return self.list_chunks(household_id, child_id, snapshot_id)


class ChinesePoemCurriculumRepository(InMemoryCurriculumKnowledgeRepository):
    def __init__(self, poems: tuple[ChinesePoemDraft, ...]) -> None:
        super().__init__()
        self._poems = poems

    def list_chinese_poems(
        self, household_id: UUID, child_id: UUID, snapshot_id: UUID
    ) -> tuple[ChinesePoemDraft, ...]:
        del household_id, child_id, snapshot_id
        return self._poems


def test_parent_uploads_multiple_curriculum_documents_into_private_drafts() -> None:
    storage = MemoryDocumentStorage()
    client = TestClient(create_app(object_storage=storage))
    parent = session_headers(client)
    response = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/imports/files",
        headers={**parent, "Idempotency-Key": "curriculum-files-1"},
        data={
            "authorization_statement": "家庭已取得本地自用材料授权",
            "grade": "3",
            "textbook_version": "人教版-三年级上册",
            "term": "上学期",
        },
        files=[
            ("files", ("数学.pdf", b"%PDF-local", "application/pdf")),
            (
                "files",
                (
                    "练习册.pdf",
                    b"%PDF-local-workbook",
                    "application/pdf",
                ),
            ),
        ],
    )

    assert response.status_code == 201
    results = response.json()
    assert [item["material"]["filename"] for item in results] == ["数学.pdf", "练习册.pdf"]
    assert [item["material"]["status"] for item in results] == ["uploaded", "uploaded"]
    assert all("object_key" not in item["material"] for item in results)
    assert len(storage.objects) == 2


def test_chinese_curriculum_is_subject_scoped_and_analysis_is_queued() -> None:
    storage = MemoryDocumentStorage()
    client = TestClient(create_app(object_storage=storage))
    parent = session_headers(client)
    enabled = client.patch(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}",
        headers={**parent, "Idempotency-Key": "enable-chinese-curriculum"},
        json={
            "display_name": "Synthetic Child A",
            "grade": 3,
            "curriculum_version": "multi-subject-2026",
            "subjects": ["math", "chinese"],
        },
    )
    uploaded = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/imports/files",
        headers={**parent, "Idempotency-Key": "chinese-curriculum-file"},
        data={
            "authorization_statement": "家庭已取得本地自用材料授权",
            "grade": "3",
            "subject": "chinese",
        },
        files=[("files", ("语文.pdf", b"%PDF-chinese", "application/pdf"))],
    )
    snapshot = uploaded.json()[0]["snapshot"]
    analysis = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/snapshots/{snapshot['id']}/analysis",
        headers={**parent, "Idempotency-Key": "chinese-analysis-queued"},
    )

    assert enabled.status_code == 200
    assert uploaded.status_code == 201
    assert uploaded.json()[0]["material"]["subject"] == "chinese"
    assert snapshot["subject"] == "chinese"
    assert analysis.status_code == 202
    assert analysis.json()["status"] == "queued"


def test_approving_chinese_curriculum_publishes_extracted_poem_questions() -> None:
    curriculum_repository = InMemoryCurriculumRepository()
    knowledge_repository = ChinesePoemCurriculumRepository(
        (
            ChinesePoemDraft(
                title="春晓",
                page_number=12,
                lines=("春眠不觉晓", "处处闻啼鸟", "夜来风雨声", "花落知多少"),
            ),
        )
    )
    chinese_repository = InMemoryChinesePracticeRepository()
    client = TestClient(
        create_app(
            curriculum_repository=curriculum_repository,
            curriculum_knowledge_repository=knowledge_repository,
            chinese_practice_repository=chinese_repository,
        )
    )
    parent = session_headers(client)
    enabled = client.patch(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}",
        headers={**parent, "Idempotency-Key": "enable-chinese-auto-poem"},
        json={
            "display_name": "Synthetic Child A",
            "grade": 3,
            "curriculum_version": "multi-subject-2026",
            "subjects": ["math", "chinese"],
        },
    )
    assert enabled.status_code == 200
    imported = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/imports",
        headers={**parent, "Idempotency-Key": "import-chinese-auto-poem"},
        json={
            "filename": "语文上册.json",
            "media_type": "application/json",
            "byte_size": 128,
            "content_sha256": "e" * 64,
            "authorization_statement": "家庭公开教材授权",
            "grade": 3,
            "subject": "chinese",
            "textbook_version": "公开语文三年级上册",
            "term": "上学期",
            "sections": [
                {
                    "title": "古诗两首",
                    "chapter": "第一单元",
                    "learning_objectives": ["背诵古诗"],
                }
            ],
        },
    )
    assert imported.status_code == 201
    result = imported.json()
    snapshot_id = result["snapshot"]["id"]
    now = datetime.now(UTC)
    knowledge_repository.save_for_testing(
        CurriculumKnowledgeMap(
            id=UUID("00000000-0000-0000-0000-000000000951"),
            household_id=UUID(HOUSEHOLD_A),
            child_id=UUID(CHILD_A),
            material_id=UUID(result["material"]["id"]),
            snapshot_id=UUID(snapshot_id),
            status=KnowledgeMapStatus.NEEDS_REVIEW,
            attempt=1,
            book_summary="古诗两首",
            page_count=1,
            analyzed_page_count=1,
            provider="newapi",
            model="chinese-model",
            schema_version="chinese-curriculum-book-analysis.v2",
            prompt_version="chinese-curriculum-book-consolidation.v2",
            created_at=now,
            updated_at=now,
        )
    )

    approved = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/snapshots/{snapshot_id}/analysis/approve",
        headers={**parent, "Idempotency-Key": "approve-chinese-auto-poem"},
    )
    assert approved.status_code == 200
    content = client.get(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/chinese/content",
        headers=session_headers(client, role="child", household_id=HOUSEHOLD_A, child_id=CHILD_A),
    )

    assert content.status_code == 200
    assert len(content.json()) == 3
    assert {item["prompt"] for item in content.json()} == {
        "“春眠不觉晓”的下一句是哪一句？",
        "“处处闻啼鸟”的下一句是哪一句？",
        "“夜来风雨声”的下一句是哪一句？",
    }
    assert all(len(item["options"]) >= 2 for item in content.json())
    assert all(item["source"]["snapshot_id"] == snapshot_id for item in content.json())


def test_file_upload_uses_a_pdf_specific_provisional_title_when_metadata_is_omitted() -> None:
    storage = MemoryDocumentStorage()
    client = TestClient(create_app(object_storage=storage))
    response = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/imports/files",
        headers={**session_headers(client), "Idempotency-Key": "curriculum-files-auto-title"},
        data={
            "authorization_statement": "家庭已取得本地自用材料授权",
            "grade": "3",
        },
        files=[("files", ("三年级数学上册.pdf", b"%PDF-local", "application/pdf"))],
    )

    assert response.status_code == 201
    snapshot = response.json()[0]["snapshot"]
    assert snapshot["textbook_version"] == "待从 PDF 识别：三年级数学上册"
    assert snapshot["term"] == "待识别"


def test_public_curriculum_reuse_requires_an_approved_source_map() -> None:
    storage = MemoryDocumentStorage()
    curriculum_repository = InMemoryCurriculumRepository()
    knowledge_repository = InMemoryCurriculumKnowledgeRepository()
    client = TestClient(
        create_app(
            object_storage=storage,
            curriculum_repository=curriculum_repository,
            curriculum_knowledge_repository=knowledge_repository,
        )
    )
    parent = session_headers(client)
    payload = {
        "authorization_statement": "国家公开教材，可跨家庭复用",
        "is_public_reusable": "true",
        "grade": "3",
        "textbook_version": "人教版-三年级上册",
        "term": "上学期",
    }
    source = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/imports/files",
        headers={**parent, "Idempotency-Key": "public-curriculum-source"},
        data=payload,
        files=[("files", ("公开教材.pdf", b"%PDF-public", "application/pdf"))],
    )
    assert source.status_code == 201

    # A matching declaration alone is insufficient. Until the source map is
    # approved the new import takes the ordinary private parse path.
    unapproved = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/imports/files",
        headers={**parent, "Idempotency-Key": "public-curriculum-unapproved"},
        data=payload,
        files=[("files", ("公开教材副本.pdf", b"%PDF-public", "application/pdf"))],
    )
    assert unapproved.status_code == 201
    assert unapproved.json()[0]["material"]["status"] == "uploaded"
    assert len(storage.objects) == 2

    source_item = source.json()[0]
    now = datetime.now(UTC)
    knowledge_repository.save_for_testing(
        CurriculumKnowledgeMap(
            id=UUID("00000000-0000-0000-0000-000000000903"),
            household_id=UUID(HOUSEHOLD_A),
            child_id=UUID(CHILD_A),
            material_id=UUID(source_item["material"]["id"]),
            snapshot_id=UUID(source_item["snapshot"]["id"]),
            status=KnowledgeMapStatus.APPROVED,
            attempt=1,
            book_summary="公开教材",
            page_count=1,
            analyzed_page_count=1,
            provider="newapi",
            model="math-model",
            schema_version="curriculum-book-analysis.v1",
            prompt_version="curriculum-book-consolidation.v5",
            created_at=now,
            updated_at=now,
            reviewed_at=now,
        )
    )
    reused = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/imports/files",
        headers={**parent, "Idempotency-Key": "public-curriculum-approved"},
        data=payload,
        files=[("files", ("公开教材第三份.pdf", b"%PDF-public", "application/pdf"))],
    )

    assert reused.status_code == 201
    assert reused.json()[0]["material"]["status"] == "needs_review"
    assert reused.json()[0]["snapshot"]["reused_from_snapshot_id"] == source_item["snapshot"]["id"]
    assert len(storage.objects) == 2


def test_parent_reads_page_scoped_parsing_output_for_review() -> None:
    curriculum_repository = CurriculumWithChunks()
    client = TestClient(create_app(curriculum_repository=curriculum_repository))
    parent = session_headers(client)
    imported = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/imports",
        headers={**parent, "Idempotency-Key": "curriculum-preview-import"},
        json={
            "filename": "math.json",
            "media_type": "application/json",
            "byte_size": 128,
            "content_sha256": "c" * 64,
            "authorization_statement": "家庭自用授权",
            "grade": 3,
            "textbook_version": "人教版-三年级上册",
            "term": "上学期",
            "sections": [
                {
                    "title": "待审核页",
                    "chapter": "第 1 页",
                    "learning_objectives": ["理解题意"],
                }
            ],
        },
    )
    material = imported.json()["material"]
    snapshot = imported.json()["snapshot"]
    curriculum_repository.chunks.append(
        CurriculumChunk(
            id=UUID("00000000-0000-0000-0000-000000000411"),
            household_id=UUID(HOUSEHOLD_A),
            child_id=UUID(CHILD_A),
            material_id=UUID(material["id"]),
            snapshot_id=UUID(snapshot["id"]),
            page_number=1,
            chunk_index=0,
            title="第一单元 认识数字",
            text="数一数。图中有几个苹果？",
            confidence=0.95,
            parser_version="test",
            created_at=datetime.now(UTC),
        )
    )

    preview = client.get(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/snapshots/{snapshot['id']}/pages",
        headers=parent,
    )

    assert preview.status_code == 200
    assert preview.json() == [
        {
            "page_number": 1,
            "title": "第一单元 认识数字",
            "text": "数一数。图中有几个苹果？",
            "confidence": 0.95,
            "image_available": False,
            "image_path": None,
        }
    ]
    child_preview = client.get(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/snapshots/{snapshot['id']}/pages",
        headers=session_headers(client, role="child", household_id=HOUSEHOLD_A, child_id=CHILD_A),
    )
    assert child_preview.status_code == 403


def test_curriculum_file_upload_rejects_unsupported_format_before_storage() -> None:
    storage = MemoryDocumentStorage()
    client = TestClient(create_app(object_storage=storage))
    response = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/imports/files",
        headers={**session_headers(client), "Idempotency-Key": "curriculum-files-2"},
        data={
            "authorization_statement": "家庭自用授权",
            "grade": "3",
            "textbook_version": "本地版",
            "term": "上学期",
        },
        files=[("files", ("教材.txt", b"not a supported document", "text/plain"))],
    )

    assert response.status_code == 422
    assert response.json()["message"] == "unsupported_material_format"
    assert storage.objects == {}


def test_mixed_batch_rejects_before_writing_any_pdf() -> None:
    storage = MemoryDocumentStorage()
    client = TestClient(create_app(object_storage=storage))
    response = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/imports/files",
        headers={**session_headers(client), "Idempotency-Key": "curriculum-files-mixed"},
        data={
            "authorization_statement": "家庭自用授权",
            "grade": "3",
            "textbook_version": "本地版",
            "term": "上学期",
        },
        files=[
            ("files", ("数学.pdf", b"%PDF-local", "application/pdf")),
            ("files", ("练习册.docx", b"PK-local-docx", "application/octet-stream")),
        ],
    )

    assert response.status_code == 422
    assert response.json()["message"] == "unsupported_material_format"
    assert storage.objects == {}


def test_uploaded_document_cannot_be_published_before_text_is_parsed() -> None:
    storage = MemoryDocumentStorage()
    client = TestClient(create_app(object_storage=storage))
    parent = session_headers(client)
    uploaded = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/imports/files",
        headers={**parent, "Idempotency-Key": "curriculum-files-pending-parse"},
        data={
            "authorization_statement": "家庭自用授权",
            "grade": "3",
            "textbook_version": "本地教材",
            "term": "上学期",
        },
        files=[("files", ("数学.pdf", b"%PDF-local", "application/pdf"))],
    )
    snapshot_id = uploaded.json()[0]["snapshot"]["id"]

    published = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/snapshots/{snapshot_id}/publish",
        headers={**parent, "Idempotency-Key": "curriculum-publish-before-parse"},
    )

    assert published.status_code == 409
    assert published.json()["message"] == ("curriculum document must be parsed before publication")


def test_parent_can_delete_uploaded_material_and_private_document() -> None:
    storage = MemoryDocumentStorage()
    client = TestClient(create_app(object_storage=storage))
    parent = session_headers(client)
    uploaded = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/imports/files",
        headers={**parent, "Idempotency-Key": "curriculum-files-delete"},
        data={
            "authorization_statement": "家庭自用授权",
            "grade": "3",
            "textbook_version": "待删除教材",
            "term": "上学期",
        },
        files=[("files", ("数学.pdf", b"%PDF-local", "application/pdf"))],
    )
    assert uploaded.status_code == 201
    snapshot_id = uploaded.json()[0]["snapshot"]["id"]
    assert len(storage.objects) == 1

    deleted = client.delete(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/snapshots/{snapshot_id}",
        headers={**parent, "Idempotency-Key": "curriculum-delete-1"},
    )
    assert deleted.status_code == 204
    assert storage.objects == {}
    assert (
        client.get(
            f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum",
            headers=parent,
        ).json()
        == []
    )

    replay = client.delete(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/snapshots/{snapshot_id}",
        headers={**parent, "Idempotency-Key": "curriculum-delete-1"},
    )
    assert replay.status_code == 204
    assert replay.headers["idempotency-replayed"] == "true"


def test_curriculum_import_accepts_the_product_50_mib_boundary() -> None:
    client = TestClient(create_app())
    parent = session_headers(client)
    response = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/imports",
        headers={**parent, "Idempotency-Key": "curriculum-50-mib"},
        json={
            "filename": "边界.pdf",
            "media_type": "application/pdf",
            "byte_size": MAX_DOCUMENT_BYTES,
            "content_sha256": "c" * 64,
            "authorization_statement": "家庭自用授权",
            "grade": 3,
            "textbook_version": "边界教材",
            "term": "上学期",
            "sections": [
                {
                    "title": "边界小节",
                    "chapter": "第一单元",
                    "learning_objectives": ["理解边界"],
                }
            ],
        },
    )
    assert response.status_code == 201


def test_parent_imports_draft_and_publishes_only_after_review() -> None:
    client = TestClient(create_app())
    parent = session_headers(client)
    payload = {
        "filename": "小学数学三年级上册.pdf",
        "media_type": "application/pdf",
        "byte_size": 1024,
        "content_sha256": "a" * 64,
        "authorization_statement": "家庭已取得本地自用材料授权",
        "grade": 3,
        "textbook_version": "人教版-三年级上册",
        "term": "上学期",
        "sections": [
            {
                "title": "分数的初步认识",
                "chapter": "第五单元",
                "learning_objectives": ["认识几分之一", "比较简单分数"],
            }
        ],
    }
    imported = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/imports",
        headers={**parent, "Idempotency-Key": "curriculum-import-1"},
        json=payload,
    )
    assert imported.status_code == 201
    snapshot = imported.json()["snapshot"]
    assert snapshot["status"] == "draft"
    child_view = client.get(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum",
        headers=session_headers(client, role="child", household_id=HOUSEHOLD_A, child_id=CHILD_A),
    )
    assert child_view.status_code == 200
    assert child_view.json() == []

    published = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/snapshots/{snapshot['id']}/publish",
        headers={**parent, "Idempotency-Key": "curriculum-publish-1"},
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    child_view = client.get(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum",
        headers=session_headers(client, role="child", household_id=HOUSEHOLD_A, child_id=CHILD_A),
    )
    assert [item["id"] for item in child_view.json()] == [snapshot["id"]]

    second_import = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/imports",
        headers={**parent, "Idempotency-Key": "curriculum-import-2"},
        json={
            **payload,
            "filename": "小学数学三年级上册练习册.pdf",
            "content_sha256": "b" * 64,
            "textbook_version": "人教版-三年级上册练习册",
        },
    )
    assert second_import.status_code == 201
    second_snapshot = second_import.json()["snapshot"]
    second_published = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/snapshots/{second_snapshot['id']}/publish",
        headers={**parent, "Idempotency-Key": "curriculum-publish-2"},
    )
    assert second_published.status_code == 200
    child_view = client.get(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum",
        headers=session_headers(client, role="child", household_id=HOUSEHOLD_A, child_id=CHILD_A),
    )
    assert {item["id"] for item in child_view.json()} == {snapshot["id"], second_snapshot["id"]}
    assert {item["status"] for item in child_view.json()} == {"published"}


def test_manifest_import_rejects_non_pdf_document_media_types() -> None:
    client = TestClient(create_app())
    parent = session_headers(client)
    payload = {
        "filename": "小学数学.docx",
        "media_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "byte_size": 1024,
        "content_sha256": "b" * 64,
        "authorization_statement": "家庭自用授权",
        "grade": 3,
        "textbook_version": "本地版",
        "term": "上学期",
        "sections": [
            {
                "title": "待解析",
                "chapter": "待解析文档",
                "learning_objectives": ["等待解析"],
            }
        ],
    }
    response = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/imports",
        headers={**parent, "Idempotency-Key": "curriculum-manifest-docx"},
        json=payload,
    )

    assert response.status_code == 422


def test_recommendation_requires_parent_approval_before_creating_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    curriculum_repository = CurriculumWithChunks()
    knowledge_repository = InMemoryCurriculumKnowledgeRepository()
    app = create_app(
        curriculum_repository=curriculum_repository,
        curriculum_knowledge_repository=knowledge_repository,
    )
    app.state.newapi_config = NewApiConfig(
        True,
        "http://newapi.local",
        "key",
        "math-model",
        5,
        100_000,
    )
    client = TestClient(app)
    parent = session_headers(client)
    curriculum = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/imports",
        headers={**parent, "Idempotency-Key": "recommendation-curriculum-import"},
        json={
            "filename": "math.json",
            "media_type": "application/json",
            "byte_size": 128,
            "content_sha256": "b" * 64,
            "authorization_statement": "家庭自用授权",
            "grade": 3,
            "textbook_version": "人教版-三年级上册",
            "term": "上学期",
            "sections": [
                {
                    "title": "分数",
                    "chapter": "第五单元",
                    "learning_objectives": ["认识分数"],
                }
            ],
        },
    )
    snapshot_id = curriculum.json()["snapshot"]["id"]
    curriculum_repository.chunks.append(
        CurriculumChunk(
            id=UUID("00000000-0000-0000-0000-000000000401"),
            household_id=UUID(HOUSEHOLD_A),
            child_id=UUID(CHILD_A),
            material_id=UUID(curriculum.json()["material"]["id"]),
            snapshot_id=UUID(snapshot_id),
            page_number=86,
            chunk_index=0,
            title="分数",
            text="做一做\n把一个圆平均分成8份，涂出其中3份，涂色部分是几分之几？",
            confidence=0.95,
            parser_version="test",
            created_at=datetime.now(UTC),
        )
    )
    assert (
        client.post(
            f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/snapshots/{snapshot_id}/publish",
            headers={**parent, "Idempotency-Key": "recommendation-curriculum-publish"},
        ).status_code
        == 200
    )
    now = datetime.now(UTC)
    knowledge_map_id = UUID("00000000-0000-0000-0000-000000000901")
    point = CurriculumKnowledgePoint(
        id=UUID("00000000-0000-0000-0000-000000000902"),
        household_id=UUID(HOUSEHOLD_A),
        child_id=UUID(CHILD_A),
        material_id=UUID(curriculum.json()["material"]["id"]),
        snapshot_id=UUID(snapshot_id),
        knowledge_map_id=knowledge_map_id,
        knowledge_key="kp-fractions",
        order_index=0,
        chapter_title="第五单元",
        section_title="分数",
        title="分数的认识与比较",
        summary="理解平均分和几分之几。",
        learning_objectives=("能用分数表示平均分后的部分",),
        prerequisites=(),
        page_numbers=(86,),
        exercises=(
            CurriculumKnowledgeExercise(
                source_key="page:86:observation:0:exercise:0",
                page_number=86,
                question_text="把一个圆平均分成8份，涂出其中3份，涂色部分是几分之几？",
                visual_description="圆平均分成八份，其中三份涂色",
                requires_visual_context=True,
                difficulty="basic",
                confidence=0.95,
            ),
        ),
        confidence=0.95,
        status="approved",
        created_at=now,
        updated_at=now,
    )
    knowledge_repository.save_for_testing(
        CurriculumKnowledgeMap(
            id=knowledge_map_id,
            household_id=UUID(HOUSEHOLD_A),
            child_id=UUID(CHILD_A),
            material_id=UUID(curriculum.json()["material"]["id"]),
            snapshot_id=UUID(snapshot_id),
            status=KnowledgeMapStatus.APPROVED,
            attempt=1,
            book_summary="分数单元",
            page_count=1,
            analyzed_page_count=1,
            provider="newapi",
            model="math-model",
            schema_version="curriculum-book-analysis.v1",
            prompt_version="curriculum-book-consolidation.v1",
            created_at=now,
            updated_at=now,
            reviewed_at=now,
            knowledge_points=(point,),
        )
    )

    second_curriculum = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/imports",
        headers={**parent, "Idempotency-Key": "recommendation-second-curriculum-import"},
        json={
            "filename": "workbook.json",
            "media_type": "application/json",
            "byte_size": 128,
            "content_sha256": "d" * 64,
            "authorization_statement": "家庭自用授权",
            "grade": 3,
            "textbook_version": "人教版-三年级上册练习册",
            "term": "上学期",
            "sections": [
                {
                    "title": "分数练习",
                    "chapter": "第五单元",
                    "learning_objectives": ["巩固分数"],
                }
            ],
        },
    )
    assert second_curriculum.status_code == 201
    second_snapshot_id = second_curriculum.json()["snapshot"]["id"]
    assert (
        client.post(
            f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/curriculum/snapshots/{second_snapshot_id}/publish",
            headers={**parent, "Idempotency-Key": "recommendation-second-curriculum-publish"},
        ).status_code
        == 200
    )
    second_map_id = UUID("00000000-0000-0000-0000-000000000903")
    knowledge_repository.save_for_testing(
        CurriculumKnowledgeMap(
            id=second_map_id,
            household_id=UUID(HOUSEHOLD_A),
            child_id=UUID(CHILD_A),
            material_id=UUID(second_curriculum.json()["material"]["id"]),
            snapshot_id=UUID(second_snapshot_id),
            status=KnowledgeMapStatus.APPROVED,
            attempt=1,
            book_summary="分数练习册",
            page_count=1,
            analyzed_page_count=1,
            provider="newapi",
            model="math-model",
            schema_version="curriculum-book-analysis.v1",
            prompt_version="curriculum-book-consolidation.v5",
            created_at=now,
            updated_at=now,
            reviewed_at=now,
            knowledge_points=(
                point.model_copy(
                    update={
                        "id": UUID("00000000-0000-0000-0000-000000000904"),
                        "material_id": UUID(second_curriculum.json()["material"]["id"]),
                        "snapshot_id": UUID(second_snapshot_id),
                        "knowledge_map_id": second_map_id,
                        "knowledge_key": "kp-fractions-workbook",
                    }
                ),
            ),
        )
    )

    def plan_from_sources(
        _provider: NewApiVisionProvider, *, sources
    ) -> ProviderRecommendationPlan:
        curriculum_sources = [source for source in sources if source.source_type == "curriculum"]
        assert {str(source.snapshot_id) for source in curriculum_sources} == {
            snapshot_id,
            second_snapshot_id,
        }
        source = next(
            source for source in curriculum_sources if str(source.snapshot_id) == snapshot_id
        )
        return ProviderRecommendationPlan(
            items=(
                ProviderRecommendationItem(
                    source_keys=(source.source_key,),
                    title="分数第86页巩固",
                    reason="从已发布教材第86页练习一道分数题。",
                    knowledge_point="分数的认识与比较",
                    scheduled_offset_days=1,
                    estimated_minutes=10,
                ),
            )
        )

    monkeypatch.setattr(
        NewApiVisionProvider,
        "create_recommendation_plan",
        plan_from_sources,
    )
    generated = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/task-recommendations",
        headers={**parent, "Idempotency-Key": "recommendation-generate-1"},
        json={"child_id": CHILD_A},
    )
    assert generated.status_code == 200
    recommendation = generated.json()[0]
    assert recommendation["status"] == "pending"
    assert recommendation["task_id"] is None
    assert recommendation["snapshot_id"] == snapshot_id
    assert recommendation["title"] == "分数第86页巩固"
    assert recommendation["scheduled_for"] > datetime.now(UTC).date().isoformat()
    assert recommendation["estimated_minutes"] == 10
    assert recommendation["exercises"][0]["source_page"] == 86
    assert "涂色部分是几分之几" in recommendation["exercises"][0]["question_text"]

    before = client.get(
        f"/households/{HOUSEHOLD_A}/tasks?child_id={CHILD_A}",
        headers=parent,
    ).json()
    approved = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/task-recommendations/{recommendation['id']}/decision",
        headers={**parent, "Idempotency-Key": "recommendation-decide-1"},
        json={"decision": "approve"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["task_id"] is not None
    after = client.get(
        f"/households/{HOUSEHOLD_A}/tasks?child_id={CHILD_A}",
        headers=parent,
    ).json()
    assert len(after) == len(before) + 1
    task = next(item for item in after if item["id"] == approved.json()["task_id"])
    assert task["source_type"] == "curriculum_exercise"
    assert task["exercises"][0]["source_page"] == 86
    replayed = client.post(
        f"/households/{HOUSEHOLD_A}/children/{CHILD_A}/task-recommendations/{recommendation['id']}/decision",
        headers={**parent, "Idempotency-Key": "recommendation-decide-1"},
        json={"decision": "approve"},
    )
    assert replayed.status_code == 200
    assert replayed.json()["task_id"] == approved.json()["task_id"]
    assert len(
        client.get(
            f"/households/{HOUSEHOLD_A}/tasks?child_id={CHILD_A}",
            headers=parent,
        ).json()
    ) == len(after)
