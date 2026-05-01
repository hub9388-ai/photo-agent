from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.storage.media_store import MediaStore, get_media_store
from backend.tests.test_media_upload import build_image_bytes


def test_asset_score_uses_asset_agent_visual_pipeline_and_detects_exact_duplicates(tmp_path) -> None:
    media_store = MediaStore(root=tmp_path / "media")
    app.dependency_overrides[get_media_store] = lambda: media_store
    client = TestClient(app)
    image_bytes = build_image_bytes(size=(800, 600))

    try:
        first = client.post(
            "/api/media/upload",
            files={"file": ("dup-a.jpg", image_bytes, "image/jpeg")},
        )
        second = client.post(
            "/api/media/upload",
            files={"file": ("dup-b.jpg", image_bytes, "image/jpeg")},
        )
        assert first.status_code == 201
        assert second.status_code == 201

        response = client.post(
            "/api/agents/asset/score",
            json={
                "mediaIds": [first.json()["mediaId"], second.json()["mediaId"]],
                "cullingPreference": "balanced",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["scoringMethod"] == "asset_agent_visual_features"
    assert len(payload["assets"]) == 2
    assert payload["duplicateGroups"]
    assert any(asset["grade"] == "duplicate" for asset in payload["assets"])

    first_asset = payload["assets"][0]
    assert first_asset["metadata"]["width"] == 800
    assert first_asset["metadata"]["height"] == 600
    assert isinstance(first_asset["metadata"]["sharpness"], (int, float))
    assert any("AssetAgent 视觉质量评分" in reason for reason in first_asset["aiReasons"])


def test_asset_score_rejects_missing_media_id(tmp_path) -> None:
    app.dependency_overrides[get_media_store] = lambda: MediaStore(root=tmp_path / "media")
    client = TestClient(app)

    try:
        response = client.post(
            "/api/agents/asset/score",
            json={"mediaIds": ["media_missing"], "cullingPreference": "balanced"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["errorCode"] == "VALIDATION_ERROR"
