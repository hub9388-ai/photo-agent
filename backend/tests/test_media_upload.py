from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.storage.media_store import MediaStore, get_media_store


def build_image_bytes(*, size: tuple[int, int] = (640, 480), image_format: str = "JPEG") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color=(120, 160, 210)).save(buffer, format=image_format)
    return buffer.getvalue()


def test_upload_media_saves_original_preview_thumbnail_and_record(tmp_path) -> None:
    media_root = tmp_path / "media"
    app.dependency_overrides[get_media_store] = lambda: MediaStore(root=media_root)
    client = TestClient(app)

    try:
        response = client.post(
            "/api/media/upload",
            files={"file": ("sample.jpg", build_image_bytes(), "image/jpeg")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    payload = response.json()
    media_id = payload["mediaId"]

    assert media_id.startswith("media_")
    assert payload["fileName"] == "sample.jpg"
    assert payload["mimeType"] == "image/jpeg"
    assert payload["previewUrl"] == f"/media/previews/{media_id}.jpg"
    assert payload["metadata"]["width"] == 640
    assert payload["metadata"]["height"] == 480
    assert payload["metadata"]["privacy"] == {"gpsRedacted": False}
    assert "data" not in payload["metadata"]

    assert (media_root / "originals" / f"{media_id}.jpg").exists()
    assert (media_root / "previews" / f"{media_id}.jpg").exists()
    assert (media_root / "thumbnails" / f"{media_id}.jpg").exists()
    assert (media_root / "records" / f"{media_id}.json").exists()


def test_upload_media_rejects_unsupported_file_type(tmp_path) -> None:
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


def test_upload_media_rejects_file_over_size_limit(tmp_path) -> None:
    app.dependency_overrides[get_media_store] = lambda: MediaStore(
        root=tmp_path / "media",
        max_upload_bytes=8,
    )
    client = TestClient(app)

    try:
        response = client.post(
            "/api/media/upload",
            files={"file": ("sample.jpg", b"0123456789", "image/jpeg")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 413
