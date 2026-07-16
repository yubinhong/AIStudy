"""Add self-hosted password accounts and revocable opaque sessions.

Revision ID: 0011_account_password_session
Revises: 0010_verified_question
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_account_password_session"
down_revision: str | None = "0010_verified_question"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("household_id", "username", name="uq_accounts_household_username"),
        sa.CheckConstraint("role IN ('parent', 'child')", name="ck_accounts_role"),
        sa.CheckConstraint("status IN ('active', 'disabled')", name="ck_accounts_status"),
        sa.CheckConstraint("failed_login_count >= 0", name="ck_accounts_failed_login_count"),
        sa.CheckConstraint(
            "(role = 'child' AND child_id IS NOT NULL) OR (role = 'parent' AND child_id IS NULL)",
            name="ck_accounts_child_binding",
        ),
    )
    op.create_index("ix_accounts_household_role", "accounts", ["household_id", "role"])
    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_auth_sessions_account_active",
        "auth_sessions",
        ["account_id", "expires_at", "revoked_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_auth_sessions_account_active", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ix_accounts_household_role", table_name="accounts")
    op.drop_table("accounts")
