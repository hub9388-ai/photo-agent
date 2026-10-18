from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.storage.media_store import MediaStore, get_media_store


@pytest.fixture
def retouch_client(tmp_path):
    store = MediaStore(root=tmp_path / "media")
    app.dependency_overrides[get_media_store] = lambda: store
    try:
        with TestClient(app) as client:
            yield client, store
    finally:
        app.dependency_overrides.pop(get_media_store, None)


def upload(client):
    data = BytesIO()
    Image.new("RGB", (64, 64), "orange").save(data, format="PNG")
    response = client.post("/api/media/upload", files={"file": ("test.png", data.getvalue(), "image/png")})
    assert response.status_code == 201
    return response.json()["mediaId"], data.getvalue()


def test_retouch_exports_original_without_reencoding(retouch_client):
    client, _ = retouch_client
    media_id, original = upload(client)
    response = client.get(f"/api/media/{media_id}/retouch-source")
    assert response.status_code == 200
    assert response.content == original
    assert response.headers["x-retouch-source"] == "original"
    assert response.headers["content-type"] == "image/png"


def test_retouch_falls_back_to_preview_for_unsupported_original(retouch_client):
    client, store = retouch_client
    media_id, _ = upload(client)
    # Simulate a RAW original while retaining the upload preview.
    (store.originals_dir / f"{media_id}.png").write_bytes(b"raw placeholder")
    response = client.get(f"/api/media/{media_id}/retouch-source")
    assert response.status_code == 200
    assert response.headers["x-retouch-source"] == "preview"
    assert response.headers["content-type"] == "image/jpeg"


def test_retouch_does_not_export_paths_outside_media_root(retouch_client, tmp_path):
    client, store = retouch_client
    media_id, original = upload(client)
    external = tmp_path / "private.png"
    external.write_bytes(original)
    asset = store.get(media_id).model_copy(update={"storage_uri": str(external)})
    (store.records_dir / f"{media_id}.json").write_text(asset.model_dump_json(), encoding="utf-8")
    (store.previews_dir / f"{media_id}.jpg").unlink()
    assert client.get(f"/api/media/{media_id}/retouch-source").status_code == 404


def test_retouch_rejects_oversized_original(retouch_client):
    client, store = retouch_client
    media_id, _ = upload(client)
    with (store.originals_dir / f"{media_id}.png").open("ab") as output:
        output.truncate(20 * 1024 * 1024 + 1)
    assert client.get(f"/api/media/{media_id}/retouch-source").status_code == 413


def test_retouch_rejects_invalid_and_missing_ids(retouch_client):
    client, _ = retouch_client
    assert client.get("/api/media/invalid/retouch-source").status_code == 422
    assert client.get("/api/media/media_missing/retouch-source").status_code == 404
