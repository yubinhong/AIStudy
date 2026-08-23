"""Shared fixtures for PostgreSQL integration tests.

Durable child profiles require a real owner account.  Keeping that setup in one
place prevents tests from relying on the old in-memory synthetic UUID.
"""

from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import delete

from study_api.auth_domain import (
    AccountRecord,
    AccountRole,
    PostgresAccountRepository,
    hash_password,
)


def create_test_parent(
    accounts: PostgresAccountRepository,
    household_id: UUID,
) -> AccountRecord:
    username = f"pg-owner-{uuid4().hex}"
    account, replayed = accounts.create_parent(
        household_id,
        username,
        hash_password("SyntheticParent123!", role=AccountRole.PARENT),
        AccountRole.PARENT,
        f"pg-owner-{uuid4()}",
        sha256(username.encode("utf-8")).hexdigest(),
    )
    assert replayed is False
    return account


def delete_test_parent(accounts: PostgresAccountRepository, account_id: UUID) -> None:
    """Remove the parent and its durable receipts after child data is gone."""

    with accounts.engine.begin() as connection:
        connection.execute(
            delete(accounts._idempotency).where(accounts._idempotency.c.resource_id == account_id)
        )
        connection.execute(
            delete(accounts._audits).where(accounts._audits.c.resource_id == account_id)
        )
        connection.execute(delete(accounts._accounts).where(accounts._accounts.c.id == account_id))
