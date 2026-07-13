import pytest
from sqlalchemy import create_engine, inspect

from study_api.database import database_url

pytestmark = pytest.mark.integration


def test_learning_schema_is_at_head_in_local_postgresql() -> None:
    engine = create_engine(database_url())
    try:
        tables = inspect(engine).get_table_names()
    finally:
        engine.dispose()

    assert {
        "study_tasks",
        "study_sessions",
        "attempts",
        "idempotency_records",
        "audit_events",
        "captures",
        "capture_corrections",
    } <= set(tables)
