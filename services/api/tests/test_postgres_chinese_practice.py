from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from study_api.auth_domain import PostgresAccountRepository, hash_password
from study_api.chinese_practice import (
    ChineseAttemptRequest,
    ChinesePoemDraft,
    ChineseSkill,
    PostgresChinesePracticeRepository,
    PublishChinesePoemsRequest,
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
    poem_content_ids: list[UUID] = []
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
        snapshot_id = uuid4()
        chinese.publish_poems(
            household_id,
            child.id,
            child.grade,
            PublishChinesePoemsRequest(
                material_id=uuid4(),
                snapshot_id=snapshot_id,
                poems=(
                    ChinesePoemDraft(
                        title="春晓",
                        page_number=1,
                        lines=("春眠不觉晓", "处处闻啼鸟", "夜来风雨声", "花落知多少"),
                    ),
                ),
            ),
        )
        poem_items = [
            item
            for item in chinese.list_content(
                grade=child.grade, household_id=household_id, child_id=child.id
            )
            if item.skill is ChineseSkill.POEM
        ]
        poem_content_ids = [item.id for item in poem_items]
        content = next(item for item in poem_items if "春眠不觉晓" in item.prompt)
        request = ChineseAttemptRequest(
            content_id=content.id,
            content_revision=content.revision,
            response={"choice": "处处闻啼鸟"},
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
        assert export.chinese_review_items[0].skill is ChineseSkill.POEM
        reviews = chinese.list_reviews(household_id, child.id, child.grade, due_only=False)
        report = chinese.skill_report(household_id, child.id)
        assert len(reviews) == 1
        assert reviews[0].content_id == content.id
        assert len(report.skills) == 1
        summary = report.skills[0]
        assert summary.skill is ChineseSkill.POEM
        assert summary.attempts == 2
        assert summary.correct_attempts == 2
        assert summary.due_reviews == 0

        assert (
            chinese.publish_poems(
                household_id,
                child.id,
                child.grade,
                PublishChinesePoemsRequest(
                    material_id=uuid4(),
                    snapshot_id=snapshot_id,
                    poems=(
                        ChinesePoemDraft(
                            title="剪窗花",
                            page_number=2,
                            lines=("小剪刀，手中拿", "我学奶奶剪窗花", "剪雪花，剪梅花"),
                        ),
                    ),
                ),
            )
            == 0
        )
        assert not chinese.list_content(
            grade=child.grade, household_id=household_id, child_id=child.id
        )
        assert not chinese.list_reviews(household_id, child.id, child.grade, due_only=False)
        preserved_report = chinese.skill_report(household_id, child.id)
        assert preserved_report.skills[0].attempts == 2
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
                connection.execute(
                    delete(chinese._content).where(chinese._content.c.id.in_(poem_content_ids))
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
