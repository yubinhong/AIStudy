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
        job_columns = {column["name"] for column in inspect(engine).get_columns("ocr_jobs")}
        image_analysis_columns = {
            column["name"] for column in inspect(engine).get_columns("image_analysis_jobs")
        }
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
        "ocr_jobs",
        "image_analysis_jobs",
        "question_extractions",
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
    assert {
        "household_id",
        "capture_id",
        "child_id",
        "idempotency_key",
        "mode",
        "status",
        "attempt",
        "enqueued_at",
        "started_at",
        "finished_at",
        "result_id",
        "error_code",
    } <= job_columns
    assert {
        "household_id",
        "capture_id",
        "child_id",
        "idempotency_key",
        "request_fingerprint",
        "status",
        "attempt",
        "sanitization_schema_version",
        "sanitized_derivative_sha256",
        "created_at",
        "updated_at",
        "extraction_id",
        "error_code",
    } <= image_analysis_columns

    extraction_columns = {
        column["name"] for column in inspect(engine).get_columns("question_extractions")
    }
    assert {
        "image_analysis_job_id",
        "capture_id",
        "household_id",
        "child_id",
        "question_text",
        "options",
        "formulas",
        "confidence",
        "needs_confirmation",
    } <= extraction_columns
