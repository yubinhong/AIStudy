from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import MetaData, Table, create_engine, delete, insert, select
from sqlalchemy.engine import Connection

from study_api.database import database_url
from study_api.domain.insights_repository import PostgresInsightsRepository

pytestmark = pytest.mark.integration

HOUSEHOLD_ID = UUID("00000000-0000-0000-0000-000000000001")


def test_learning_history_cleanup_deletes_expired_details_but_preserves_open_mistakes() -> None:
    engine = create_engine(database_url(), pool_pre_ping=True)
    metadata = MetaData()
    tables = {
        name: Table(name, metadata, autoload_with=engine)
        for name in (
            "study_tasks",
            "study_sessions",
            "captures",
            "image_analysis_jobs",
            "question_extractions",
            "verified_questions",
            "tutor_turns",
            "mistake_records",
            "review_schedules",
            "review_attempts",
            "idempotency_records",
            "child_profiles",
            "accounts",
        )
    }
    # The local integration database may intentionally lag optional modules.
    # Bind only the four tables used by this retention method so the test does
    # not require unrelated English-practice migrations.
    insights = PostgresInsightsRepository.__new__(PostgresInsightsRepository)
    insights._engine = engine
    insights._mistakes = tables["mistake_records"]
    insights._idempotency = tables["idempotency_records"]
    insights._verified_questions = tables["verified_questions"]
    insights._tutor_turns = tables["tutor_turns"]
    now = datetime.now(UTC)
    old = now - timedelta(days=190)
    cutoff = now - timedelta(days=180)
    task_id, session_id = uuid4(), uuid4()
    child_id, parent_id = uuid4(), uuid4()
    created: dict[str, tuple[UUID, UUID]] = {}

    def add_question(
        connection: Connection,
        label: str,
        verified_at: datetime,
        mistake_status: str | None = None,
    ) -> None:
        # This helper only writes synthetic IDs/text into the isolated integration database.
        execute = connection.execute
        capture_id, job_id, extraction_id = uuid4(), uuid4(), uuid4()
        question_id, turn_id = uuid4(), uuid4()
        created[label] = (question_id, turn_id)
        execute(
            insert(tables["captures"]).values(
                id=capture_id,
                household_id=HOUSEHOLD_ID,
                child_id=child_id,
                session_id=session_id,
                media_type="image/jpeg",
                byte_size=128,
                content_sha256=label.ljust(64, "0")[:64],
                status="corrected",
                version=1,
                created_at=verified_at,
            )
        )
        execute(
            insert(tables["image_analysis_jobs"]).values(
                id=job_id,
                household_id=HOUSEHOLD_ID,
                capture_id=capture_id,
                child_id=child_id,
                idempotency_key=f"history-job-{label}",
                request_fingerprint=label.ljust(64, "1")[:64],
                status="succeeded",
                attempt=1,
                sanitization_schema_version="privacy-sanitization.v1",
                sanitized_derivative_sha256=label.ljust(64, "2")[:64],
                created_at=verified_at,
                updated_at=verified_at,
                extraction_id=extraction_id,
            )
        )
        execute(
            insert(tables["question_extractions"]).values(
                id=extraction_id,
                image_analysis_job_id=job_id,
                capture_id=capture_id,
                household_id=HOUSEHOLD_ID,
                child_id=child_id,
                schema_version="question-extraction.v1",
                subject="math",
                question_text=f"Synthetic {label} question",
                options=[],
                formulas=[],
                has_diagram=False,
                has_handwriting=False,
                detected_answer=None,
                question_region_count=1,
                confidence=Decimal("0.99"),
                needs_confirmation=True,
                answer_state="blank",
                answer_state_confidence=Decimal("0.99"),
                answer_steps=[],
                created_at=verified_at,
            )
        )
        execute(
            insert(tables["verified_questions"]).values(
                id=question_id,
                household_id=HOUSEHOLD_ID,
                child_id=child_id,
                capture_id=capture_id,
                extraction_id=extraction_id,
                version=1,
                subject="math",
                question_text=f"Synthetic {label} question",
                options=[],
                formulas=[],
                has_diagram=False,
                has_handwriting=False,
                answer_text=None,
                answer_state="blank",
                answer_state_confidence=Decimal("0.99"),
                answer_steps=[],
                evidence_confirmed=True,
                verified_by="child",
                verified_at=verified_at,
            )
        )
        execute(
            insert(tables["tutor_turns"]).values(
                id=turn_id,
                household_id=HOUSEHOLD_ID,
                child_id=child_id,
                verified_question_id=question_id,
                level=1,
                policy_version="synthetic-retention.v1",
                provider="local",
                model="synthetic",
                mode="mistake_explanation",
                answer_state="blank",
                prompt="Synthetic bounded hint",
                next_step="Synthetic next step",
                requires_child_response=True,
                solution_steps=[],
                curriculum_sources=[],
                revealed_elements=[],
                cost_cents=0,
                created_at=verified_at,
            )
        )
        for resource_type, resource_id in (
            ("verified_question", question_id),
            ("tutor_turn", turn_id),
        ):
            execute(
                insert(tables["idempotency_records"]).values(
                    household_id=HOUSEHOLD_ID,
                    operation=f"history-{resource_type}-{label}",
                    idempotency_key=f"history-{resource_type}-{label}",
                    fingerprint=label.ljust(64, "3")[:64],
                    resource_type=resource_type,
                    resource_id=resource_id,
                    created_at=verified_at,
                )
            )
        if mistake_status is None:
            return
        mistake_id = uuid4()
        resolved_at = old if mistake_status == "resolved" else None
        execute(
            insert(tables["mistake_records"]).values(
                id=mistake_id,
                household_id=HOUSEHOLD_ID,
                child_id=child_id,
                verified_question_id=question_id,
                session_id=session_id,
                reason="synthetic_retention",
                status=mistake_status,
                created_at=old,
                resolved_at=resolved_at,
            )
        )
        execute(
            insert(tables["review_schedules"]).values(
                id=uuid4(),
                household_id=HOUSEHOLD_ID,
                child_id=child_id,
                mistake_id=mistake_id,
                due_at=old,
                interval_days=1,
                repetitions=3 if mistake_status == "resolved" else 0,
                last_outcome="correct" if mistake_status == "resolved" else None,
                created_at=old,
                updated_at=old,
            )
        )
        if mistake_status == "resolved":
            execute(
                insert(tables["review_attempts"]).values(
                    id=uuid4(),
                    household_id=HOUSEHOLD_ID,
                    child_id=child_id,
                    mistake_id=mistake_id,
                    verified_question_id=question_id,
                    answer_summary="Synthetic correct review",
                    submitted_answer="1",
                    evidence_confirmed=True,
                    outcome="correct",
                    policy_version="review-policy.v2",
                    created_at=old,
                )
            )

    try:
        with engine.begin() as connection:
            child_values = {
                "id": child_id,
                "household_id": HOUSEHOLD_ID,
                "display_name": "Synthetic retention child",
                "grade": 2,
                "curriculum_version": "math-demo-2026",
                "subjects": ["math"],
                "created_at": now,
                "updated_at": now,
            }
            if "owner_account_id" in tables["child_profiles"].c:
                connection.execute(
                    insert(tables["accounts"]).values(
                        id=parent_id,
                        household_id=HOUSEHOLD_ID,
                        username=f"history-parent-{uuid4()}",
                        role="parent",
                        child_id=None,
                        password_hash="synthetic-not-a-real-password-hash",
                        must_change_password=False,
                        status="active",
                        failed_login_count=0,
                        locked_until=None,
                        created_at=now,
                        updated_at=now,
                    )
                )
                child_values["owner_account_id"] = parent_id
            connection.execute(insert(tables["child_profiles"]).values(**child_values))
            connection.execute(
                insert(tables["study_tasks"]).values(
                    id=task_id,
                    household_id=HOUSEHOLD_ID,
                    child_id=child_id,
                    title="Synthetic retention task",
                    subject="math",
                    scheduled_for=date.today(),
                    status="assigned",
                    version=1,
                    created_at=old,
                )
            )
            connection.execute(
                insert(tables["study_sessions"]).values(
                    id=session_id,
                    household_id=HOUSEHOLD_ID,
                    child_id=child_id,
                    task_id=task_id,
                    task_version=1,
                    status="active",
                    started_at=old,
                )
            )
            add_question(connection, "expired", old)
            add_question(connection, "resolved", old, "resolved")
            add_question(connection, "open", old, "open")
            add_question(connection, "recent", now - timedelta(days=2))

        result = insights.cleanup_expired_learning_history(cutoff)

        assert result.resolved_mistakes_deleted == 1
        assert result.tutor_turns_deleted == 2
        assert result.verified_questions_deleted == 2
        with engine.connect() as connection:
            remaining_questions = set(connection.scalars(select(tables["verified_questions"].c.id)))
            remaining_turns = set(connection.scalars(select(tables["tutor_turns"].c.id)))
            remaining_mistakes = set(
                connection.scalars(select(tables["mistake_records"].c.verified_question_id))
            )
        assert remaining_questions == {created["open"][0], created["recent"][0]}
        assert remaining_turns == {created["open"][1], created["recent"][1]}
        assert remaining_mistakes == {created["open"][0]}
    finally:
        with engine.begin() as connection:
            connection.execute(
                delete(tables["idempotency_records"]).where(
                    tables["idempotency_records"].c.operation.like("history-%")
                )
            )
            connection.execute(
                delete(tables["tutor_turns"]).where(tables["tutor_turns"].c.child_id == child_id)
            )
            connection.execute(
                delete(tables["mistake_records"]).where(
                    tables["mistake_records"].c.child_id == child_id
                )
            )
            connection.execute(
                delete(tables["verified_questions"]).where(
                    tables["verified_questions"].c.child_id == child_id
                )
            )
            connection.execute(
                delete(tables["question_extractions"]).where(
                    tables["question_extractions"].c.child_id == child_id
                )
            )
            connection.execute(
                delete(tables["image_analysis_jobs"]).where(
                    tables["image_analysis_jobs"].c.child_id == child_id
                )
            )
            connection.execute(
                delete(tables["captures"]).where(tables["captures"].c.child_id == child_id)
            )
            connection.execute(
                delete(tables["study_sessions"]).where(
                    tables["study_sessions"].c.child_id == child_id
                )
            )
            connection.execute(
                delete(tables["study_tasks"]).where(tables["study_tasks"].c.child_id == child_id)
            )
            connection.execute(
                delete(tables["child_profiles"]).where(tables["child_profiles"].c.id == child_id)
            )
            connection.execute(
                delete(tables["accounts"]).where(tables["accounts"].c.id == parent_id)
            )
        engine.dispose()
