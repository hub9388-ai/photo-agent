from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.storage.media_store import MediaNotFoundError, MediaStore, get_media_store


class MissingMediaStore:
    def get(self, media_id: str):
        raise MediaNotFoundError(f"Media not found: {media_id}")


def test_job_not_found_uses_structured_error_response() -> None:
    client = TestClient(app)

    response = client.get("/api/jobs/job_missing")

    assert response.status_code == 404
    assert response.json()["errorCode"] == "JOB_NOT_FOUND"


def test_validation_error_uses_structured_error_response() -> None:
    client = TestClient(app)

    response = client.post("/api/jobs", json={"agents": []})

    assert response.status_code == 422
    payload = response.json()
    assert payload["errorCode"] == "VALIDATION_ERROR"
    assert payload["detail"]["errors"]
    assert "input" not in payload["detail"]["errors"][0]


def test_create_job_rejects_missing_media_id_before_agent_runs() -> None:
    app.dependency_overrides[get_media_store] = lambda: MissingMediaStore()
    client = TestClient(app)

    try:
        response = client.post(
            "/api/jobs",
            json={
                "type": "photo_review",
                "media_ids": ["media_missing"],
                "agents": ["post", "coach"],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    payload = response.json()
    assert payload["errorCode"] == "VALIDATION_ERROR"
    assert payload["detail"]["missingMediaIds"] == ["media_missing"]


def test_create_job_rejects_post_coach_job_without_media_ids() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/jobs",
        json={"type": "photo_review", "media_ids": [], "agents": ["post", "coach"]},
    )

    assert response.status_code == 400
    assert response.json()["errorCode"] == "VALIDATION_ERROR"


def test_media_upload_error_uses_media_error_code(tmp_path) -> None:
    app.dependency_overrides[get_media_store] = lambda: MediaStore(root=tmp_path / "media")
    client = TestClient(app)

    try:
        response = client.post(
            "/api/media/upload",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 415
    assert response.json()["errorCode"] == "MEDIA_INVALID_TYPE"


def test_handoff_missing_source_job_uses_structured_error_code() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/handoff",
        json={
            "source_job_id": "job_001",
            "source_agent": "asset",
            "target_agent": "post",
            "media_ids": ["media_001"],
        },
    )

    assert response.status_code == 404
    assert response.json()["errorCode"] == "JOB_NOT_FOUND"
