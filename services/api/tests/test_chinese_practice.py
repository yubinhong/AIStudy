from uuid import UUID

from auth_helpers import DEFAULT_HOUSEHOLD_ID, session_headers
from fastapi.testclient import TestClient

from study_api.chinese_practice import (
    ChineseContentItem,
    ChineseContentSource,
    ChineseSkill,
    ConceptEvidenceSpec,
    OrderedTokensSpec,
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


def test_chinese_content_requires_subject_and_is_grade_bounded() -> None:
    client = TestClient(create_app())
    path = f"/households/{DEFAULT_HOUSEHOLD_ID}/children/{CHILD_ID}/chinese/content"

    disabled = client.get(path, headers=session_headers(client, role="child", child_id=CHILD_ID))
    _enable_chinese(client)
    enabled = client.get(path, headers=session_headers(client, role="child", child_id=CHILD_ID))

    assert disabled.status_code == 409
    assert enabled.status_code == 200
    assert {item["skill"] for item in enabled.json()} == {"sentence", "reading"}
    assert all(item["source"]["license_status"] == "cleared" for item in enabled.json())
    assert all("answer_spec" not in item for item in enabled.json())


def test_child_submits_chinese_attempt_idempotently_and_parent_cannot_submit() -> None:
    client = TestClient(create_app())
    _enable_chinese(client)
    root = f"/households/{DEFAULT_HOUSEHOLD_ID}/children/{CHILD_ID}/chinese"
    child_headers = session_headers(client, role="child", child_id=CHILD_ID)
    items = client.get(f"{root}/content", headers=child_headers).json()
    reading = next(item for item in items if item["skill"] == "reading")
    payload = {
        "content_id": reading["id"],
        "content_revision": reading["revision"],
        "response": {
            "answer": "因为小树长出了新叶",
            "evidence": "小树长出了嫩绿的新叶",
        },
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


def test_chinese_attempt_rejects_unbounded_or_unknown_response_fields() -> None:
    client = TestClient(create_app())
    _enable_chinese(client)
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
