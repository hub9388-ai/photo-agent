from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_openapi_exposes_job_and_handoff_contracts() -> None:
    client = TestClient(app)

    schema = client.get("/openapi.json").json()

    assert "/api/jobs" in schema["paths"]
    assert "/api/jobs/{job_id}/agents/{agent}/retry" in schema["paths"]
    assert "/api/jobs/{job_id}/events" in schema["paths"]
    assert "/api/jobs/{job_id}/results" in schema["paths"]
    assert "/api/learning/profile" in schema["paths"]
    assert "/api/agents/plan/run" in schema["paths"]
    assert "/api/projects/{project_id}/assets/import" in schema["paths"]
    assert "/api/projects/{project_id}/assets" in schema["paths"]
    assert "/api/handoff" in schema["paths"]
    assert "AgentRetryResponse" in schema["components"]["schemas"]
    assert "AssetImportResponse" in schema["components"]["schemas"]
    assert "CreateJobResponse" in schema["components"]["schemas"]
    assert "ErrorResponse" in schema["components"]["schemas"]
    assert "JobDetailResponse" in schema["components"]["schemas"]
    assert "JobListResponse" in schema["components"]["schemas"]
    assert "JobResultsResponse" in schema["components"]["schemas"]
    assert "LearningProfileResponse" in schema["components"]["schemas"]
    assert "PlanRunRequest" in schema["components"]["schemas"]
    assert "PlanRunResponse" in schema["components"]["schemas"]
    assert "UploadMediaResponse" in schema["components"]["schemas"]
    assert "HandoffResponse" in schema["components"]["schemas"]
    assert "HandoffRequest" in schema["components"]["schemas"]

    job_post = schema["paths"]["/api/jobs"]["post"]
    response_ref = job_post["responses"]["202"]["content"]["application/json"]["schema"]["$ref"]
    assert response_ref.endswith("/CreateJobResponse")

    events_get = schema["paths"]["/api/jobs/{job_id}/events"]["get"]
    assert "response_model" not in events_get
    assert "text/event-stream" in events_get["responses"]["200"]["content"]

    retry_post = schema["paths"]["/api/jobs/{job_id}/agents/{agent}/retry"]["post"]
    retry_ref = retry_post["responses"]["202"]["content"]["application/json"]["schema"]["$ref"]
    assert retry_ref.endswith("/AgentRetryResponse")

    plan_post = schema["paths"]["/api/agents/plan/run"]["post"]
    plan_ref = plan_post["responses"]["202"]["content"]["application/json"]["schema"]["$ref"]
    assert plan_ref.endswith("/PlanRunResponse")

    asset_import = schema["paths"]["/api/projects/{project_id}/assets/import"]["post"]
    asset_import_ref = asset_import["responses"]["202"]["content"]["application/json"]["schema"]["$ref"]
    assert asset_import_ref.endswith("/AssetImportResponse")
