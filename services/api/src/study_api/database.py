"""PostgreSQL connection configuration for local synthetic integration tests."""

import os

LOCAL_DATABASE_URL = "postgresql+psycopg://study:study_local_only@127.0.0.1:5432/study"


def database_url() -> str:
    """Read the service database URL without logging credentials."""

    return os.environ.get("DATABASE_URL", LOCAL_DATABASE_URL)
