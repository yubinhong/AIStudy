from fastapi.testclient import TestClient

from study_api.main import app


def test_health_endpoint_matches_contract() -> None:
    response = TestClient(app).get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "study-api", "version": "0.11.0"}
