from study_api.curriculum_analysis_jobs import (
    _analyze_curriculum_page_batch,
    _page_payloads,
    _validate_book_coverage,
    main,
)
from study_api.domain.curriculum_knowledge import (
    ProviderBookAnalysis,
    ProviderBookChapter,
    ProviderBookKnowledgePoint,
    ProviderExercise,
    ProviderKnowledgeObservation,
    ProviderPageAnalysis,
)
from study_api.domain.models import Subject
from study_api.newapi_provider import CurriculumProviderPage, NewApiProviderError


def _book(*, start_page: int = 1, end_page: int = 2) -> ProviderBookAnalysis:
    return ProviderBookAnalysis(
        schema_version="curriculum-book-analysis.v1",
        book_summary="从教材原页归纳的整本知识结构。",
        chapters=(
            ProviderBookChapter(
                title="第一章",
                start_page=start_page,
                end_page=end_page,
                summary="认识图形关系。",
                knowledge_points=(
                    ProviderBookKnowledgePoint(
                        knowledge_key="kp-shape-position",
                        section_title="位置",
                        title="上下前后",
                        summary="根据原页图形判断物体的位置关系。",
                        learning_objectives=("能用上下前后描述位置",),
                        prerequisites=(),
                        page_numbers=(start_page,),
                        exercise_keys=(),
                        confidence=0.9,
                    ),
                ),
            ),
        ),
    )


def test_page_payload_preserves_visual_semantics_and_opaque_exercise_key() -> None:
    page = ProviderPageAnalysis(
        page_number=1,
        chapter_title="第一章",
        section_title="位置",
        summary="结合图画认识位置。",
        knowledge_observations=(
            ProviderKnowledgeObservation(
                title="上下关系",
                summary="根据物体图画判断上下关系。",
                learning_objectives=("能判断两个物体的上下关系",),
                prerequisites=(),
                exercises=(
                    ProviderExercise(
                        question_text="把铅笔放在书本的下面。",
                        visual_description="页面展示一本书和一支铅笔的可移动贴图。",
                        requires_visual_context=True,
                        difficulty="basic",
                        confidence=0.92,
                    ),
                ),
                confidence=0.9,
            ),
        ),
        confidence=0.9,
    )

    payloads, exercises = _page_payloads((page,))

    exercise = payloads[0]["knowledge_observations"][0]["exercises"][0]
    assert exercise["exercise_key"] == "page:1:observation:0:exercise:0"
    assert exercise["requires_visual_context"] is True
    assert "书和一支铅笔" in exercise["visual_description"]
    assert exercises[exercise["exercise_key"]].page_number == 1


def test_book_map_allows_nonknowledge_pages_but_rejects_invented_pages() -> None:
    _validate_book_coverage(_book(), {1, 2})
    _validate_book_coverage(_book(start_page=1, end_page=1), {1, 2})

    try:
        _validate_book_coverage(_book(start_page=1, end_page=3), {1, 2})
    except ValueError as error:
        assert "unknown page" in str(error)
    else:
        raise AssertionError("invented page must reject the entire knowledge map")


def test_curriculum_page_batch_splits_413_until_each_page_fits(caplog) -> None:
    class SinglePageProvider:
        last_call_metrics = None

        def __init__(self) -> None:
            self.batch_sizes: list[int] = []

        def analyze_curriculum_pages(self, pages, *, subject):
            del subject
            self.batch_sizes.append(len(pages))
            if len(pages) > 1:
                raise NewApiProviderError("oversized", code="provider_http_413")
            return (
                ProviderPageAnalysis(
                    page_number=pages[0].page_number,
                    chapter_title="合成章节",
                    section_title="合成小节",
                    summary="合成页面摘要。",
                    confidence=0.9,
                ),
            )

    provider = SinglePageProvider()
    pages = tuple(
        CurriculumProviderPage(
            page_number=page_number,
            extracted_text="synthetic-only",
            image_bytes=b"synthetic",
        )
        for page_number in range(1, 5)
    )

    with caplog.at_level("WARNING", logger="study_api.curriculum_analysis_jobs"):
        analyses, metrics = _analyze_curriculum_page_batch(
            provider,
            pages,
            subject=Subject.CHINESE,  # type: ignore[arg-type]
        )

    assert [page.page_number for page in analyses] == [1, 2, 3, 4]
    assert provider.batch_sizes == [4, 2, 1, 1, 2, 1, 1]
    assert metrics == ()
    assert caplog.text.count("curriculum_provider_batch_split") == 3
    assert "synthetic-only" not in caplog.text


def test_curriculum_page_batch_preserves_single_page_413() -> None:
    class RejectingProvider:
        last_call_metrics = None

        def analyze_curriculum_pages(self, pages, *, subject):
            del pages, subject
            raise NewApiProviderError("oversized", code="provider_http_413")

    page = CurriculumProviderPage(
        page_number=1,
        extracted_text="synthetic-only",
        image_bytes=b"synthetic",
    )

    try:
        _analyze_curriculum_page_batch(
            RejectingProvider(),
            (page,),
            subject=Subject.CHINESE,  # type: ignore[arg-type]
        )
    except NewApiProviderError as error:
        assert error.code == "provider_http_413"
    else:
        raise AssertionError("a single oversized page must remain a visible failure")


def test_one_shot_worker_exits_cleanly_when_newapi_is_disabled(
    monkeypatch,
) -> None:
    monkeypatch.setenv("STUDY_NEWAPI_ENABLED", "false")
    monkeypatch.setattr("sys.argv", ["run_curriculum_analysis_worker.py"])

    assert main() == 0
