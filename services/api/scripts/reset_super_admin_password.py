"""Reset the sole self-hosted super-admin password from the server console.

This recovery path deliberately has no HTTP endpoint. Run it only from the
trusted API container or host with database access; it never prints, logs, or
accepts the new password as a command-line argument.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from study_api.auth_domain import AuthService, PostgresAccountRepository
from study_api.domain.models import AccountRole


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset the self-hosted super-admin password")
    parser.add_argument("--username", default="admin", help="super-admin username (default: admin)")
    parser.add_argument(
        "--confirm-super-admin-recovery",
        action="store_true",
        help="required acknowledgement before changing credentials",
    )
    args = parser.parse_args()
    if not args.confirm_super_admin_recovery:
        parser.error("--confirm-super-admin-recovery is required")

    password = getpass.getpass("New super-admin password: ")
    confirmation = getpass.getpass("Confirm new super-admin password: ")
    if password != confirmation:
        print("Passwords do not match.", file=sys.stderr)
        return 2

    repository = PostgresAccountRepository()
    try:
        account = repository.get_by_username(args.username)
        if account is None or account.role is not AccountRole.SUPER_ADMIN:
            print("Named account is not the super administrator.", file=sys.stderr)
            return 3
        AuthService(repository).reset_password(account.id, password)
    finally:
        repository.close()
    print("Password reset. The next login must change this temporary password.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
