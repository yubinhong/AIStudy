from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from study_api.auth_domain import PostgresAccountRepository, hash_password
from study_api.chinese_practice import (
    ChineseAttemptRequest,
    ChineseSkill,
    PostgresChinesePracticeRepository,
)
from study_api.domain.insights_repository import PostgresInsightsRepository
from study_api.domain.models import AccountRole, CreateChildRequest, Subject
from study_api.domain.sql_profile_repository import PostgresProfileRepository

pytestmark = pytest.mark.integration


def test_postgres_concurrent_chinese_attempts_merge_review_and_export() -> None:
    profiles = PostgresProfileRepository()
    chinese = PostgresChinesePracticeRepository()
    insights = PostgresInsightsRepository()
    accounts = PostgresAccountRepository()
    household_id = uuid4()
    username = f"pg-chinese-{uuid4().hex}"
    parent, _ = accounts.create_parent(
        household_id,
        username,
        hash_password("SyntheticParent123!", role=AccountRole.PARENT),
        AccountRole.PARENT,
        f"pg-chinese-parent-{uuid4()}",
        sha256(username.encode()).hexdigest(),
    )
    child = None
    try:
        child, _ = profiles.create_child(
            household_id,
            CreateChildRequest(
                display_name="Synthetic concurrent Chinese child",
                grade=3,
                curriculum_version="multi-demo-2026",
                subjects=[Subject.MATH, Subject.CHINESE],
            ),
            f"pg-chinese-child-{uuid4()}",
            owner_account_id=parent.id,
        )
        content = next(
            item
            for item in chinese.list_content(grade=child.grade)
            if item.skill is ChineseSkill.READING
        )
        request = ChineseAttemptRequest(
            content_id=content.id,
            content_revision=content.revision,
            response={"answer": "小树长出了新叶", "evidence": "小树长出了嫩绿的新叶"},
            elapsed_ms=1_200,
        )

        def submit() -> tuple[UUID, bool]:
            repository = PostgresChinesePracticeRepository()
            try:
                attempt, replayed = repository.submit_attempt(
                    household_id,
                    child.id,
                    child.grade,
                    request,
                    f"pg-chinese-attempt-{uuid4()}",
                )
                return attempt.id, replayed
            finally:
                repository.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [future.result() for future in (pool.submit(submit) for _ in range(2))]

        assert len({attempt_id for attempt_id, _ in results}) == 2
        assert all(replayed is False for _, replayed in results)

        export, replayed = insights.export_child(
            household_id, child.id, f"pg-chinese-export-{uuid4()}"
        )
        assert replayed is False
        assert len(export.chinese_attempts) == 2
        assert all(attempt.result.correct for attempt in export.chinese_attempts)
        assert all(attempt.response == request.response for attempt in export.chinese_attempts)
        assert len(export.chinese_review_items) == 1
        assert export.chinese_review_items[0].strength == 2
        assert export.chinese_review_items[0].skill is ChineseSkill.READING
        reviews = chinese.list_reviews(household_id, child.id, child.grade, due_only=False)
        report = chinese.skill_report(household_id, child.id)
        assert len(reviews) == 1
        assert reviews[0].content_id == content.id
        assert len(report.skills) == 1
        summary = report.skills[0]
        assert summary.skill is ChineseSkill.READING
        assert summary.attempts == 2
        assert summary.correct_attempts == 2
        assert summary.due_reviews == 0
    finally:
        with profiles.engine.begin() as connection:
            if child is not None:
                connection.execute(
                    delete(chinese._idempotency).where(
                        chinese._idempotency.c.operation == f"chinese_attempt:{child.id}"
                    )
                )
                connection.execute(
                    delete(insights._idempotency).where(
                        insights._idempotency.c.operation == f"export_child:{child.id}"
                    )
                )
                connection.execute(
                    delete(profiles._idempotency).where(
                        profiles._idempotency.c.resource_id == child.id
                    )
                )
                connection.execute(
                    delete(profiles._audits).where(profiles._audits.c.resource_id == child.id)
                )
                connection.execute(
                    delete(profiles._children).where(profiles._children.c.id == child.id)
                )
                assert (
                    connection.execute(
                        select(chinese._attempts).where(chinese._attempts.c.child_id == child.id)
                    ).first()
                    is None
                )
                assert (
                    connection.execute(
                        select(chinese._reviews).where(chinese._reviews.c.child_id == child.id)
                    ).first()
                    is None
                )
            connection.execute(
                delete(accounts._idempotency).where(
                    accounts._idempotency.c.resource_id == parent.id
                )
            )
            connection.execute(
                delete(accounts._audits).where(accounts._audits.c.resource_id == parent.id)
            )
            connection.execute(
                delete(accounts._accounts).where(accounts._accounts.c.id == parent.id)
            )
        insights.close()
        chinese.close()
        profiles.close()
        accounts.close()
