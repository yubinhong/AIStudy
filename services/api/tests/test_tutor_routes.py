from datetime import UTC, datetime
from uuid import UUID, uuid4

from auth_helpers import session_headers
from fastapi import FastAPI
from fastapi.testclient import TestClient

from study_api.curriculum_analysis_jobs import InMemoryCurriculumKnowledgeRepository
from study_api.domain.curriculum_knowledge import (
    CurriculumKnowledgeExercise,
    CurriculumKnowledgeMap,
    CurriculumKnowledgePoint,
    KnowledgeMapStatus,
)
from study_api.main import create_app
from study_api.newapi_provider import NewApiConfig, NewApiVisionProvider
from study_api.privacy_models import VerifyQuestionRequest
from study_api.tutor_policy import DetailedSolution, GeneratedTutorHint

HOUSEHOLD_A = "00000000-0000-0000-0000-000000000001"
CHILD_A = "00000000-0000-0000-0000-000000000101"


def _principal(
    client: TestClient, *, role: str = "parent", child_id: str | None = None
) -> dict[str, str]:
    return session_headers(client, role=role, child_id=child_id)


def _corrected_capture(client: TestClient) -> dict[str, object]:
    task = client.post(
        f"/households/{HOUSEHOLD_A}/tasks",
        headers={**_principal(client), "Idempotency-Key": f"tutor-task-{uuid4()}"},
        json={
            "child_id": CHILD_A,
            "title": "Tutor synthetic task",
            "subject": "math",
            "scheduled_for": "2026-07-15",
        },
    ).json()
    session = client.post(
        f"/households/{HOUSEHOLD_A}/tasks/{task['id']}/sessions",
        headers={
            **_principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": f"tutor-session-{uuid4()}",
        },
        json={"expected_task_version": task["version"]},
    ).json()
    capture = client.post(
        f"/households/{HOUSEHOLD_A}/sessions/{session['id']}/captures",
        headers={
            **_principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": f"tutor-capture-{uuid4()}",
        },
        json={
            "media_type": "image/jpeg",
            "byte_size": 100,
            "content_sha256": "a" * 64,
        },
    ).json()
    correction = client.post(
        f"/households/{HOUSEHOLD_A}/captures/{capture['id']}/corrections",
        headers={
            **_principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": f"tutor-correction-{uuid4()}",
        },
        json={"expected_capture_version": capture["version"], "corrected_text": "3/4 + 1/8 = ?"},
    )
    assert correction.status_code == 201
    return correction.json()


def _verified_question(
    app: FastAPI,
    capture_id: str,
    *,
    answer_state: str = "unclear",
    evidence_confirmed: bool = False,
) -> str:
    record, _ = app.state.verified_question_repository.create(
        UUID(HOUSEHOLD_A),
        UUID(CHILD_A),
        UUID(capture_id),
        uuid4(),
        VerifyQuestionRequest(
            expected_capture_version=2,
            question_text="3/4 + 1/8 = ?",
            formulas=("3/4 + 1/8",),
            answer_text="7/8",
            answer_state=answer_state,
            evidence_confirmed=evidence_confirmed,
        ),
        "child",
        f"seed-verified-{uuid4()}",
    )
    return str(record.id)


def _fraction_curriculum_repository() -> InMemoryCurriculumKnowledgeRepository:
    repository = InMemoryCurriculumKnowledgeRepository()
    now = datetime.now(UTC)
    snapshot_id = UUID("00000000-0000-0000-0000-000000000401")
    material_id = UUID("00000000-0000-0000-0000-000000000402")
    knowledge_map_id = UUID("00000000-0000-0000-0000-000000000403")
    point = CurriculumKnowledgePoint(
        id=UUID("00000000-0000-0000-0000-000000000404"),
        household_id=UUID(HOUSEHOLD_A),
        child_id=UUID(CHILD_A),
        material_id=material_id,
        snapshot_id=snapshot_id,
        knowledge_map_id=knowledge_map_id,
        knowledge_key="kp-fraction-addition",
        order_index=0,
        chapter_title="分数",
        section_title="同分母与异分母分数加法",
        title="分数加法",
        summary="通过统一分母后计算分数加法，结果要约成最简分数。",
        learning_objectives=("理解分母不同不能直接相加", "会先统一分母再计算"),
        prerequisites=("认识分子和分母",),
        page_numbers=(42,),
        exercises=(
            CurriculumKnowledgeExercise(
                source_key="page:42:exercise:0",
                page_number=42,
                question_text="3/4 + 1/8 = ?",
                requires_visual_context=False,
                difficulty="basic",
                confidence=0.99,
            ),
        ),
        confidence=0.99,
        status="approved",
        created_at=now,
        updated_at=now,
    )
    repository.save_for_testing(
        CurriculumKnowledgeMap(
            id=knowledge_map_id,
            household_id=UUID(HOUSEHOLD_A),
            child_id=UUID(CHILD_A),
            material_id=material_id,
            snapshot_id=snapshot_id,
            status=KnowledgeMapStatus.APPROVED,
            attempt=1,
            book_summary="分数教材。",
            chapters=(),
            page_count=80,
            analyzed_page_count=80,
            schema_version="curriculum-book-analysis.v1",
            prompt_version="curriculum-book-v1",
            created_at=now,
            updated_at=now,
            reviewed_at=now,
            knowledge_points=(point,),
        )
    )
    return repository


def test_tutor_hint_requires_corrected_capture_and_returns_no_answer() -> None:
    app = create_app()
    client = TestClient(app)
    correction = _corrected_capture(client)
    verified_question_id = _verified_question(app, str(correction["capture_id"]))
    first_payload = {
        "verified_question_id": verified_question_id,
        "level": 1,
    }
    first = client.post(
        f"/households/{HOUSEHOLD_A}/tutor/hints",
        headers={
            **_principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": "tutor-hint-000",
        },
        json=first_payload,
    )
    assert first.status_code == 200
    payload = {
        "verified_question_id": verified_question_id,
        "level": 2,
    }
    response = client.post(
        f"/households/{HOUSEHOLD_A}/tutor/hints",
        headers={
            **_principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": "tutor-hint-001",
        },
        json=payload,
    )
    assert response.status_code == 200
    assert response.json()["provider"] == "local-policy"
    assert response.json()["verified_question_id"] == verified_question_id
    assert response.json()["builds_on_turn_id"] == first.json()["id"]
    assert response.json()["direct_answer"] is None
    assert "7/8" not in response.text

    replay = client.post(
        f"/households/{HOUSEHOLD_A}/tutor/hints",
        headers={
            **_principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": "tutor-hint-001",
        },
        json=payload,
    )
    assert replay.status_code == 200
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.json()["id"] == response.json()["id"]


def test_tutor_hint_rejects_parent_or_child_mismatch() -> None:
    app = create_app()
    client = TestClient(app)
    correction = _corrected_capture(client)
    verified_question_id = _verified_question(app, str(correction["capture_id"]))
    payload = {
        "verified_question_id": verified_question_id,
        "level": 1,
    }
    parent = client.post(
        f"/households/{HOUSEHOLD_A}/tutor/hints",
        headers={**_principal(client), "Idempotency-Key": "tutor-hint-parent"},
        json=payload,
    )
    mismatch = client.post(
        f"/households/{HOUSEHOLD_A}/tutor/hints",
        headers={
            **_principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": "tutor-hint-mismatch",
        },
        json={**payload, "verified_question_id": str(uuid4())},
    )
    assert parent.status_code == 403
    assert mismatch.status_code == 404


def test_tutor_hint_rejects_client_supplied_verified_question_payload() -> None:
    client = TestClient(create_app())
    response = client.post(
        f"/households/{HOUSEHOLD_A}/tutor/hints",
        headers={
            **_principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": "tutor-forged-question",
        },
        json={"verified_question": {"question_text": "forged"}, "level": 1},
    )
    assert response.status_code == 422


def test_level_three_returns_and_persists_complete_verified_solution(
    monkeypatch,
) -> None:
    app = create_app(curriculum_knowledge_repository=_fraction_curriculum_repository())
    app.state.newapi_config = NewApiConfig(
        True, "https://newapi.local", "key", "vision-model", 5, 100_000
    )
    client = TestClient(app)
    correction = _corrected_capture(client)
    verified_question_id = _verified_question(
        app,
        str(correction["capture_id"]),
        answer_state="blank",
        evidence_confirmed=True,
    )

    def fake_solution(self, *, curriculum_scope, **_kwargs) -> DetailedSolution:
        assert curriculum_scope["knowledge_key"] == "kp-fraction-addition"
        assert curriculum_scope["learning_objectives"] == [
            "理解分母不同不能直接相加",
            "会先统一分母再计算",
        ]
        return DetailedSolution(
            steps=("先统一分母。", "再相加并约分。"),
            final_answer="7/8",
            verification="把结果换回同分母后核对。",
        )

    monkeypatch.setattr(NewApiVisionProvider, "create_detailed_solution", fake_solution)
    response = client.post(
        f"/households/{HOUSEHOLD_A}/tutor/hints",
        headers={
            **_principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": "tutor-complete-solution",
        },
        json={
            "verified_question_id": verified_question_id,
            "level": 3,
            "mode": "mistake_explanation",
        },
    )

    assert response.status_code == 200
    assert response.json()["solution_steps"] == ["先统一分母。", "再相加并约分。"]
    assert response.json()["direct_answer"] == "7/8"
    assert response.json()["verification"] == "把结果换回同分母后核对。"
    assert response.json()["requires_child_response"] is False
    assert response.json()["curriculum_sources"] == [
        {
            "snapshot_id": "00000000-0000-0000-0000-000000000401",
            "page_number": 42,
            "title": "分数加法",
            "confidence": 0.99,
        }
    ]


def test_level_three_solves_a_question_without_an_approved_curriculum_scope(monkeypatch) -> None:
    app = create_app()
    app.state.newapi_config = NewApiConfig(
        True, "https://newapi.local", "key", "vision-model", 5, 100_000
    )
    client = TestClient(app)
    correction = _corrected_capture(client)
    verified_question_id = _verified_question(
        app,
        str(correction["capture_id"]),
        answer_state="blank",
        evidence_confirmed=True,
    )

    def fake_solution(self, *, curriculum_scope, **_kwargs) -> DetailedSolution:
        assert curriculum_scope is None
        return DetailedSolution(
            steps=("先找出图中已知的页数。", "用总页数减去已看的页数表示剩余页数。"),
            final_answer="剩下的页数=总页数-已经看过的页数。",
            verification="把已经看过的页数和剩余页数相加，应当等于总页数。",
        )

    monkeypatch.setattr(NewApiVisionProvider, "create_detailed_solution", fake_solution)
    response = client.post(
        f"/households/{HOUSEHOLD_A}/tutor/hints",
        headers={
            **_principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": "tutor-complete-solution-ungrounded",
        },
        json={
            "verified_question_id": verified_question_id,
            "level": 3,
            "mode": "mistake_explanation",
        },
    )

    assert response.status_code == 200
    assert response.json()["policy_version"] == "general-solution-policy.v1"
    assert response.json()["curriculum_sources"] == []
    assert response.json()["solution_steps"] == [
        "先找出图中已知的页数。",
        "用总页数减去已看的页数表示剩余页数。",
    ]
    assert response.json()["direct_answer"] == "剩下的页数=总页数-已经看过的页数。"


def test_cloud_l1_and_l2_are_question_specific_and_progressive(monkeypatch) -> None:
    app = create_app()
    app.state.newapi_config = NewApiConfig(
        True, "https://newapi.local", "key", "vision-model", 5, 100_000
    )
    client = TestClient(app)
    correction = _corrected_capture(client)
    verified_question_id = _verified_question(
        app,
        str(correction["capture_id"]),
        answer_state="blank",
        evidence_confirmed=True,
    )

    def fake_hint(self, *, level: int, previous_hint, **_kwargs) -> GeneratedTutorHint:
        if level == 1:
            assert previous_hint is None
            return GeneratedTutorHint(
                prompt="先看清两个分数表示的是不是同样大小的份。",
                next_step="指出分母不同会让哪一个关系不能直接比较。",
                child_action="说出这道题最先要处理的关系。",
                revealed_elements=("known_and_unknown", "key_relationship"),
            )
        assert previous_hint is not None
        return GeneratedTutorHint(
            prompt="沿着刚才的分母关系，先选择一个共同的计数单位。",
            next_step="只写出通分的骨架，暂时不要完成相加。",
            child_action="写出第一步通分并说明依据。",
            revealed_elements=(
                "key_relationship",
                "method_choice",
                "first_step_scaffold",
            ),
        )

    monkeypatch.setattr(NewApiVisionProvider, "create_tutor_hint", fake_hint)
    first = client.post(
        f"/households/{HOUSEHOLD_A}/tutor/hints",
        headers={
            **_principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": "cloud-tutor-l1",
        },
        json={
            "verified_question_id": verified_question_id,
            "level": 1,
            "mode": "mistake_explanation",
        },
    )
    second = client.post(
        f"/households/{HOUSEHOLD_A}/tutor/hints",
        headers={
            **_principal(client, role="child", child_id=CHILD_A),
            "Idempotency-Key": "cloud-tutor-l2",
        },
        json={
            "verified_question_id": verified_question_id,
            "level": 2,
            "mode": "mistake_explanation",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["provider"] == second.json()["provider"] == "newapi"
    assert second.json()["builds_on_turn_id"] == first.json()["id"]
    assert second.json()["answer_exposure"] == "none"
    assert second.json()["direct_answer"] is None
