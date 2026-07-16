"""Issue one self-hosted household bearer token from environment configuration."""

import argparse
import os
from datetime import timedelta
from uuid import UUID

from study_api.auth_tokens import issue_token
from study_api.domain.models import DemoRole


def main() -> int:
    parser = argparse.ArgumentParser(description="Issue a local study household token")
    parser.add_argument("--household-id", required=True, type=UUID)
    parser.add_argument("--role", choices=[role.value for role in DemoRole], required=True)
    parser.add_argument("--child-id", type=UUID)
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    secret = os.environ.get("STUDY_AUTH_SECRET", "")
    print(
        issue_token(
            secret,
            args.household_id,
            DemoRole(args.role),
            args.child_id,
            ttl=timedelta(days=args.days),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
