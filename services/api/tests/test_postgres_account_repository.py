from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete

from study_api.auth_domain import (
    DuplicateUsernameError,
    PostgresAccountRepository,
    hash_password,
)
from study_api.domain.models import AccountRole, CreateChildRequest, Subject
from study_api.domain.sql_profile_repository import PostgresProfileRepository

pytestmark = pytest.mark.integration

HOUSEHOLD_A = UUID("00000000-0000-0000-0000-000000000001")


def test_duplicate_username_is_a_domain_conflict_not_a_database_error() -> None:
    profiles = PostgresProfileRepository()
    accounts = PostgresAccountRepository()
    child, _ = profiles.create_child(
        HOUSEHOLD_A,
        CreateChildRequest(
            display_name="Synthetic account child",
            grade=2,
            curriculum_version="math-demo-2026",
            subjects=[Subject.MATH],
        ),
        f"pg-account-profile-{uuid4()}",
    )
    username = f"synthetic-account-{uuid4()}"
    account_id: UUID | None = None
    try:
        account, replayed = accounts.create_child(
            HOUSEHOLD_A,
            username,
            hash_password("synthetic-child-pass", role=AccountRole.CHILD),
            child.id,
            f"pg-account-create-{uuid4()}",
            "synthetic-first-request",
        )
        account_id = account.id
        assert replayed is False

        with pytest.raises(DuplicateUsernameError):
            accounts.create_child(
                HOUSEHOLD_A,
                username,
                hash_password("synthetic-child-pass", role=AccountRole.CHILD),
                child.id,
                f"pg-account-duplicate-{uuid4()}",
                "synthetic-duplicate-request",
            )
    finally:
        resource_ids = {child.id}
        if account_id is not None:
            resource_ids.add(account_id)
        with accounts.engine.begin() as connection:
            connection.execute(
                delete(accounts._idempotency).where(
                    accounts._idempotency.c.resource_id.in_(resource_ids)
                )
            )
            connection.execute(
                delete(accounts._audits).where(accounts._audits.c.resource_id.in_(resource_ids))
            )
            if account_id is not None:
                connection.execute(
                    delete(accounts._accounts).where(accounts._accounts.c.id == account_id)
                )
            connection.execute(
                delete(profiles._children).where(profiles._children.c.id == child.id)
            )
        accounts.close()
        profiles.close()
