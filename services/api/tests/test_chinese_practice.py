from datetime import UTC, datetime
from uuid import UUID, uuid4

from auth_helpers import DEFAULT_HOUSEHOLD_ID, session_headers
from fastapi.testclient import TestClient

from study_api.chinese_practice import (
    ChineseContentItem,
    ChineseContentReview,
    ChineseContentSource,
    ChineseSkill,
    ConceptEvidenceSpec,
    ExactChoiceSpec,
    InMemoryChinesePracticeRepository,
    NormalizedTextSetSpec,
    OrderedTokensSpec,
    PublishChinesePoemsRequest,
    score_chinese,
)
from study_api.main import create_app

CHILD_ID = UUID("00000000-0000-0000-0000-000000000101")


def _enable_chinese(client: TestClient) -> None:
    response = client.patch(
        f"/households/{DEFAULT_HOUSEHOLD_ID}/children/{CHILD_ID}",
        headers={
            **session_headers(client),
            "Idempotency-Key": "enable-chinese-subject-001",
        },
        json={
            "display_name": "Synthetic Child A",
            "grade": 3,
            "curriculum_version": "multi-demo-2026",
            "subjects": ["math", "chinese"],
        },
    )
    assert response.status_code == 200


def _publish_test_poems(client: TestClient) -> None:
    client.app.state.chinese_practice_repository.publish_poems(
        DEFAULT_HOUSEHOLD_ID,
        CHILD_ID,
        3,
        PublishChinesePoemsRequest(
            material_id=uuid4(),
            snapshot_id=uuid4(),
            poems=(
                {
                    "title": "春晓",
                    "page_number": 12,
                    "lines": ("春眠不觉晓", "处处闻啼鸟", "夜来风雨声", "花落知多少"),
                },
            ),
        ),
    )


def test_chinese_content_requires_subject_and_is_grade_bounded() -> None:
    client = TestClient(create_app())
    path = f"/households/{DEFAULT_HOUSEHOLD_ID}/children/{CHILD_ID}/chinese/content"

    disabled = client.get(path, headers=session_headers(client, role="child", child_id=CHILD_ID))
    _enable_chinese(client)
    _publish_test_poems(client)
    enabled = client.get(path, headers=session_headers(client, role="child", child_id=CHILD_ID))

    assert disabled.status_code == 409
    assert enabled.status_code == 200
    assert {item["skill"] for item in enabled.json()} == {"poem"}
    assert all(item["source"]["license_status"] == "private_authorized" for item in enabled.json())
    assert all("answer_spec" not in item for item in enabled.json())


def test_child_submits_chinese_attempt_idempotently_and_parent_cannot_submit() -> None:
    client = TestClient(create_app())
    _enable_chinese(client)
    _publish_test_poems(client)
    root = f"/households/{DEFAULT_HOUSEHOLD_ID}/children/{CHILD_ID}/chinese"
    child_headers = session_headers(client, role="child", child_id=CHILD_ID)
    items = client.get(f"{root}/content", headers=child_headers).json()
    poem = next(item for item in items if item["skill"] == "poem")
    payload = {
        "content_id": poem["id"],
        "content_revision": poem["revision"],
        "response": {"choice": poem["options"][0]},
        "elapsed_ms": 12000,
    }
    headers = {**child_headers, "Idempotency-Key": "chinese-attempt-001"}

    created = client.post(f"{root}/attempts", headers=headers, json=payload)
    replay = client.post(f"{root}/attempts", headers=headers, json=payload)
    conflict = client.post(
        f"{root}/attempts",
        headers=headers,
        json={**payload, "elapsed_ms": 13000},
    )
    parent = client.post(
        f"{root}/attempts",
        headers={**session_headers(client), "Idempotency-Key": "chinese-parent-001"},
        json=payload,
    )

    assert created.status_code == 201
    assert created.json()["result"]["correct"] is True
    assert created.json()["result"]["scoring_version"] == "chinese-score.v1"
    assert replay.status_code == 200
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.json() == created.json()
    assert conflict.status_code == 409
    assert parent.status_code == 403


def test_chinese_review_queue_and_parent_skill_report_are_role_scoped() -> None:
    client = TestClient(create_app())
    _enable_chinese(client)
    _publish_test_poems(client)
    root = f"/households/{DEFAULT_HOUSEHOLD_ID}/children/{CHILD_ID}/chinese"
    child_headers = session_headers(client, role="child", child_id=CHILD_ID)
    content = client.get(f"{root}/content", headers=child_headers).json()
    poem = next(item for item in content if item["skill"] == "poem")

    submitted = client.post(
        f"{root}/attempts",
        headers={**child_headers, "Idempotency-Key": "chinese-report-attempt-001"},
        json={
            "content_id": poem["id"],
            "content_revision": poem["revision"],
            "response": {"choice": poem["options"][0]},
            "elapsed_ms": 900,
        },
    )
    reviews = client.get(f"{root}/reviews?due_only=false", headers=child_headers)
    parent_report = client.get(f"{root}/skill-report", headers=session_headers(client))
    parent_reviews = client.get(f"{root}/reviews", headers=session_headers(client))
    child_report = client.get(f"{root}/skill-report", headers=child_headers)

    assert submitted.status_code == 201
    assert reviews.status_code == 200
    assert reviews.json()[0]["content_id"] == poem["id"]
    assert parent_report.status_code == 200
    assert parent_report.json()["skills"] == [
        {
            "skill": "poem",
            "attempts": 1,
            "correct_attempts": 1,
            "due_reviews": 0,
            "last_attempt_at": submitted.json()["created_at"],
        }
    ]
    assert parent_reviews.status_code == 403
    assert child_report.status_code == 403


def test_deterministic_scorer_handles_order_and_evidence_without_provider() -> None:
    source = ChineseContentSource(type="original", source_id="test", license_status="cleared")
    ordered = ChineseContentItem(
        id=UUID("20000000-0000-0000-0000-000000000001"),
        revision=1,
        grade_min=1,
        grade_max=6,
        skill=ChineseSkill.SENTENCE,
        task_group="language_accumulation",
        title="排序",
        prompt="排序",
        answer_spec=OrderedTokensSpec(type="ordered_tokens", tokens=("春风", "来了")),
        knowledge_key="test-order",
        source=source,
    )
    reading = ordered.model_copy(
        update={
            "id": UUID("20000000-0000-0000-0000-000000000002"),
            "skill": ChineseSkill.READING,
            "answer_spec": ConceptEvidenceSpec(
                type="concept_evidence",
                required_concepts=(("新叶", "嫩叶"),),
                evidence_spans=("长出了新叶",),
            ),
        }
    )

    assert score_chinese(ordered, {"tokens": ["春风", "来了"]}).correct is True
    partial = score_chinese(reading, {"answer": "长出嫩叶", "evidence": "别的句子"})
    assert partial.score == 1
    assert partial.feedback_tags == ("evidence_missing",)


def test_chinese_golden_scorer_covers_every_learning_skill() -> None:
    cases = (
        (
            ChineseSkill.PINYIN,
            ExactChoiceSpec(type="exact_choice", answer="青"),
            {"choice": "青"},
        ),
        (
            ChineseSkill.CHARACTER,
            NormalizedTextSetSpec(type="normalized_text_set", accepted=("晴", "晴天")),
            {"text": " 晴。"},
        ),
        (
            ChineseSkill.VOCABULARY,
            NormalizedTextSetSpec(type="normalized_text_set", accepted=("清新", "空气清新")),
            {"text": "空气清新"},
        ),
        (
            ChineseSkill.SENTENCE,
            OrderedTokensSpec(type="ordered_tokens", tokens=("小鸟", "飞过", "天空")),
            {"tokens": ["小鸟", "飞过", "天空"]},
        ),
        (
            ChineseSkill.READING,
            ConceptEvidenceSpec(
                type="concept_evidence",
                required_concepts=(("新叶", "嫩叶"),),
                evidence_spans=("小树长出了嫩绿的新叶",),
            ),
            {"answer": "因为小树长出了嫩叶", "evidence": "小树长出了嫩绿的新叶"},
        ),
        (
            ChineseSkill.RECITATION,
            ExactChoiceSpec(type="exact_choice", answer="花落知多少"),
            {"choice": "花落知多少"},
        ),
        (
            ChineseSkill.EXPRESSION,
            ConceptEvidenceSpec(
                type="concept_evidence",
                required_concepts=(("开头",), ("结尾",)),
                evidence_spans=("先说开头，再写结尾",),
            ),
            {"answer": "有开头和结尾", "evidence": "先说开头，再写结尾"},
        ),
        (
            ChineseSkill.POEM,
            ExactChoiceSpec(type="exact_choice", answer="处处闻啼鸟"),
            {"choice": "处处闻啼鸟"},
        ),
    )

    for index, (skill, answer_spec, response) in enumerate(cases):
        item = ChineseContentItem(
            id=UUID(f"20000000-0000-0000-0000-{index + 10:012d}"),
            revision=1,
            grade_min=1,
            grade_max=6,
            skill=skill,
            task_group="golden",
            title=f"{skill.value} golden",
            prompt="请作答",
            answer_spec=answer_spec,
            knowledge_key=f"golden-{skill.value}",
            source=ChineseContentSource(
                type="original",
                source_id="golden",
                license_status="cleared",
            ),
        )
        result = score_chinese(item, response)
        assert result.correct is True, skill
        assert (
            result.score == result.max_score == (2 if answer_spec.type == "concept_evidence" else 1)
        )
        assert result.feedback_tags == ("correct",)


def test_chinese_golden_scorer_exposes_bounded_retry_feedback() -> None:
    item = ChineseContentItem(
        id=UUID("20000000-0000-0000-0000-000000000020"),
        revision=1,
        grade_min=1,
        grade_max=6,
        skill=ChineseSkill.PINYIN,
        task_group="golden",
        title="拼音重试",
        prompt="选择正确读音",
        answer_spec=ExactChoiceSpec(type="exact_choice", answer="青"),
        knowledge_key="golden-retry",
        source=ChineseContentSource(type="original", source_id="golden", license_status="cleared"),
    )

    result = score_chinese(item, {"choice": "请"})

    assert result.correct is False
    assert result.score == 0
    assert result.feedback_tags == ("choice_retry",)
    assert result.correct_answer == "青"


def test_pending_original_content_is_not_available_to_learners() -> None:
    practice = InMemoryChinesePracticeRepository()
    pending = ChineseContentItem(
        id=UUID("20000000-0000-0000-0000-000000000021"),
        revision=1,
        grade_min=1,
        grade_max=6,
        skill=ChineseSkill.PINYIN,
        task_group="review-gate",
        title="待审核原创内容",
        prompt="不能展示",
        answer_spec=ExactChoiceSpec(type="exact_choice", answer="青"),
        knowledge_key="review-gate",
        source=ChineseContentSource(type="original", source_id="pending", license_status="cleared"),
    )
    practice._content[pending.id] = pending

    assert practice.list_content(grade=1) == []

    approved = pending.model_copy(
        update={
            "id": UUID("20000000-0000-0000-0000-000000000022"),
            "source": pending.source.model_copy(
                update={
                    "review": ChineseContentReview(
                        status="approved",
                        rights_evidence_sha256="a" * 64,
                        reviewed_at=datetime.now(UTC),
                        reviewer_role="project_owner",
                    )
                }
            ),
        }
    )
    practice._content[approved.id] = approved

    assert practice.list_content(grade=1) == [approved]


def test_retired_demos_are_not_listed_and_private_poems_are_child_scoped() -> None:
    client = TestClient(create_app())
    _enable_chinese(client)
    _publish_test_poems(client)
    root = f"/households/{DEFAULT_HOUSEHOLD_ID}/children/{CHILD_ID}/chinese"
    headers = session_headers(client, role="child", child_id=CHILD_ID)

    grade_three = client.get(f"{root}/content", headers=headers)
    assert grade_three.status_code == 200
    assert {item["skill"] for item in grade_three.json()} == {"poem"}
    assert all(
        item["source"]["license_status"] == "private_authorized" and "answer_spec" not in item
        for item in grade_three.json()
    )


def test_chinese_attempt_rejects_unbounded_or_unknown_response_fields() -> None:
    client = TestClient(create_app())
    _enable_chinese(client)
    _publish_test_poems(client)
    root = f"/households/{DEFAULT_HOUSEHOLD_ID}/children/{CHILD_ID}/chinese"
    child_headers = session_headers(client, role="child", child_id=CHILD_ID)
    content = client.get(f"{root}/content", headers=child_headers).json()[0]
    base = {
        "content_id": content["id"],
        "content_revision": content["revision"],
        "elapsed_ms": 100,
    }

    unknown = client.post(
        f"{root}/attempts",
        headers={**child_headers, "Idempotency-Key": "chinese-bounded-001"},
        json={**base, "response": {"raw_payload": "not allowed"}},
    )
    oversized = client.post(
        f"{root}/attempts",
        headers={**child_headers, "Idempotency-Key": "chinese-bounded-002"},
        json={**base, "response": {"text": "字" * 1001}},
    )

    assert unknown.status_code == 422
    assert oversized.status_code == 422


def test_child_cannot_submit_content_outside_their_grade() -> None:
    client = TestClient(create_app())
    _enable_chinese(client)
    root = f"/households/{DEFAULT_HOUSEHOLD_ID}/children/{CHILD_ID}/chinese"
    child_headers = session_headers(client, role="child", child_id=CHILD_ID)
    response = client.post(
        f"{root}/attempts",
        headers={**child_headers, "Idempotency-Key": "chinese-grade-bound-001"},
        json={
            "content_id": "10000000-0000-0000-0000-000000000001",
            "content_revision": 1,
            "response": {"choice": "青"},
            "elapsed_ms": 100,
        },
    )

    assert response.status_code == 404
