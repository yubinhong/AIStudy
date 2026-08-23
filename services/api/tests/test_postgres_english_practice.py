from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from postgres_helpers import create_test_parent, delete_test_parent
from sqlalchemy import delete, select

from study_api.auth_domain import PostgresAccountRepository
from study_api.domain.insights_repository import PostgresInsightsRepository
from study_api.domain.models import CreateChildRequest, Subject
from study_api.domain.sql_profile_repository import PostgresProfileRepository
from study_api.english_practice import (
    EnglishActiveSessionError,
    EnglishLevel,
    EnglishLiveConfig,
    EnglishSessionStatus,
    FakeEnglishLiveProvider,
    PostgresEnglishPracticeRepository,
    UpdateEnglishPracticeSettings,
)

pytestmark = pytest.mark.integration


def test_postgres_english_settings_session_export_and_child_cascade() -> None:
    profiles = PostgresProfileRepository()
    english = PostgresEnglishPracticeRepository(engine=profiles.engine)
    insights = PostgresInsightsRepository()
    accounts = PostgresAccountRepository()
    household_id = uuid4()
    owner = create_test_parent(accounts, household_id)
    child, _ = profiles.create_child(
        household_id,
        CreateChildRequest(
            display_name="Synthetic English child",
            grade=3,
            curriculum_version="math-demo-2026",
            subjects=[Subject.MATH],
        ),
        f"pg-english-child-{uuid4()}",
        owner_account_id=owner.id,
    )
    config = EnglishLiveConfig(enabled=True, provider="fake", allow_test_provider=True)
    provider = FakeEnglishLiveProvider()
    try:
        settings, replayed = english.update_settings(
            household_id,
            child.id,
            child.owner_account_id,
            UpdateEnglishPracticeSettings(
                enabled=True,
                level=EnglishLevel.A1,
                consent_version=config.consent_version,
                expected_version=0,
            ),
            f"pg-english-settings-{uuid4()}",
        )
        assert replayed is False
        assert settings.version == 1
        session, _ = english.start_session(
            household_id,
            child.id,
            "greetings",
            config,
            provider,
            f"pg-english-start-{uuid4()}",
        )
        english.record_audio(session.id, input_ms=20, output_ms=40)
        english.record_turn(session.id)
        completed, _ = english.complete_session(
            household_id,
            child.id,
            session.id,
            EnglishSessionStatus.COMPLETED,
            f"pg-english-complete-{uuid4()}",
        )
        assert completed.input_audio_ms == 20
        assert completed.output_audio_ms == 40
        assert completed.turn_count == 1

        export, _ = insights.export_child(household_id, child.id, f"pg-english-export-{uuid4()}")
        assert export.english_practice_settings is not None
        assert export.english_practice_settings.level is EnglishLevel.A1
        assert len(export.english_practice_sessions) == 1

        with profiles.engine.begin() as connection:
            connection.execute(
                delete(english._idempotency).where(
                    english._idempotency.c.resource_id.in_([child.id, completed.id])
                )
            )
            connection.execute(
                delete(profiles._idempotency).where(profiles._idempotency.c.resource_id == child.id)
            )
            connection.execute(
                delete(profiles._children).where(profiles._children.c.id == child.id)
            )
            assert (
                connection.execute(
                    select(english._settings).where(english._settings.c.child_id == child.id)
                ).first()
                is None
            )
            assert (
                connection.execute(
                    select(english._sessions).where(english._sessions.c.child_id == child.id)
                ).first()
                is None
            )
    finally:
        with profiles.engine.begin() as connection:
            connection.execute(
                delete(profiles._idempotency).where(
                    profiles._idempotency.c.operation == f"export_child:{child.id}"
                )
            )
            connection.execute(
                delete(profiles._children).where(profiles._children.c.id == child.id)
            )
        delete_test_parent(accounts, owner.id)
        insights.close()
        english.close()
        profiles.close()
        accounts.close()


def test_postgres_enforces_one_active_english_session_under_concurrency() -> None:
    profiles = PostgresProfileRepository()
    english = PostgresEnglishPracticeRepository(engine=profiles.engine)
    accounts = PostgresAccountRepository()
    household_id = uuid4()
    owner = create_test_parent(accounts, household_id)
    child, _ = profiles.create_child(
        household_id,
        CreateChildRequest(
            display_name="Synthetic concurrent English child",
            grade=4,
            curriculum_version="math-demo-2026",
            subjects=[Subject.MATH],
        ),
        f"pg-english-concurrent-child-{uuid4()}",
        owner_account_id=owner.id,
    )
    config = EnglishLiveConfig(enabled=True, provider="fake", allow_test_provider=True)
    provider = FakeEnglishLiveProvider()
    english.update_settings(
        household_id,
        child.id,
        child.owner_account_id,
        UpdateEnglishPracticeSettings(
            enabled=True,
            level=EnglishLevel.A2,
            consent_version=config.consent_version,
            expected_version=0,
        ),
        f"pg-english-concurrent-settings-{uuid4()}",
    )

    def start() -> str:
        repository = PostgresEnglishPracticeRepository()
        try:
            session, _ = repository.start_session(
                household_id,
                child.id,
                "school",
                config,
                provider,
                f"pg-english-concurrent-start-{uuid4()}",
            )
            return str(session.id)
        finally:
            repository.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [pool.submit(start) for _ in range(2)]
        successes = 0
        conflicts = 0
        for result in results:
            try:
                result.result()
                successes += 1
            except EnglishActiveSessionError:
                conflicts += 1
        assert (successes, conflicts) == (1, 1)
    finally:
        with profiles.engine.begin() as connection:
            connection.execute(
                delete(english._idempotency).where(
                    english._idempotency.c.operation == f"english_settings:{child.id}"
                )
            )
            connection.execute(
                delete(profiles._idempotency).where(profiles._idempotency.c.resource_id == child.id)
            )
            connection.execute(
                delete(profiles._children).where(profiles._children.c.id == child.id)
            )
        delete_test_parent(accounts, owner.id)
        profiles.close()
        english.close()
        accounts.close()
