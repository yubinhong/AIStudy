import pytest
from sqlalchemy import create_engine, inspect

from study_api.database import database_url

pytestmark = pytest.mark.integration


def test_learning_schema_is_at_head_in_local_postgresql() -> None:
    engine = create_engine(database_url())
    try:
        tables = inspect(engine).get_table_names()
        columns = {column["name"] for column in inspect(engine).get_columns("captures")}
        result_columns = {column["name"] for column in inspect(engine).get_columns("ocr_results")}
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
        "ocr_results",
        "ocr_candidates",
    } <= set(tables)
    assert {
        "object_key",
        "retention_class",
        "expires_at",
        "deletion_status",
        "parent_saved",
    } <= columns

    assert {
        "provider",
        "model",
        "model_version",
        "schema_version",
        "confidence",
        "requires_manual_confirmation",
    } <= result_columns
