"""Reproduce the reported 5464x3070 edit in a disposable session, no model calls.

Reads the reported photo through the main API, preserves the user's existing session.
Never logs cookies, credentials or asset URLs.
"""
import hashlib
import io
import json
import secrets
import time
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MEDIA_ID = "media_6ca0c3faabf742308647f43b05c048f6"


def main():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                        urllib.request.HTTPCookieProcessor(CookieJar()))

    def request(path, payload=None, raw=None, content_type="application/json"):
        data = json.dumps(payload).encode() if payload is not None else raw
        req = urllib.request.Request("http://127.0.0.1:7301" + path, data=data,
                                     headers={"Content-Type": content_type})
        with opener.open(req, timeout=30) as response:
            return json.loads(response.read())

    source_url = f"http://127.0.0.1:8000/api/media/{MEDIA_ID}/retouch-source"
    with opener.open(source_url, timeout=30) as response:
        original_bytes = response.read()
    with Image.open(io.BytesIO(original_bytes)) as image:
        assert image.size == (5464, 3070)
    request("/api/auth/register", {"username": "large_adjust_" + secrets.token_hex(5),
                                   "password": secrets.token_urlsafe(24)})
    boundary = "large" + secrets.token_hex(8)
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="large-photo.jpg"\r\n'
            'Content-Type: image/jpeg\r\n\r\n').encode() + original_bytes + f"\r\n--{boundary}--\r\n".encode()
    asset = request("/api/assets", raw=body, content_type=f"multipart/form-data; boundary={boundary}")
    original = request("/api/sessions", {"current_asset_id": asset["id"], "title": "Large adjustment isolated acceptance"})
    prefix = f"/api/sessions/{original['id']}"
    params = {"tint": 0, "clarity": 0, "shadows": .22, "contrast": .31, "vibrance": .13,
              "vignette": 0, "sharpness": .35, "brightness": .1, "highlights": -.35,
              "saturation": .12, "temperature": 0, "expected_revision": original["revision"]}
    start = time.monotonic()
    run = request(prefix + "/tools", {"tool": "adjust_image", "params": params})["run"]
    while run["status"] in {"queued", "running"}:
        if time.monotonic() - start > 90:
            raise TimeoutError("Large adjustment worker did not finish")
        time.sleep(.5)
        run = request("/api/runs/" + run["id"])
    assert run["status"] == "succeeded", run.get("error")
    current = request(prefix)
    assert current["original_asset_id"] == asset["id"] and current["current_asset_id"] != asset["id"]
    generated = next(a for a in current["assets"] if a["id"] == current["current_asset_id"])
    assert (generated["width"], generated["height"]) == (5464, 3070)
    assert generated["image_format"] == "PNG" and generated["size_bytes"] > 20 * 1024 * 1024
    with opener.open(generated["url"], timeout=30) as response:
        output = response.read()
    with Image.open(io.BytesIO(output)) as image:
        image.load()
        assert image.size == (5464, 3070)
    history = request(prefix + "/history")
    applied = next(e for e in reversed(history) if e["action"] == "adjust_image")
    assert all(applied["params"][k] == v for k, v in params.items())
    restored = request(prefix + "/undo", {})
    assert restored["current_asset_id"] == asset["id"]
    with opener.open(source_url, timeout=30) as response:
        assert hashlib.sha256(response.read()).digest() == hashlib.sha256(original_bytes).digest()
    report = {"status": "passed", "scope": "same photo and failed run numeric parameters; isolated new session, no browser quality assessment",
              "media_id": MEDIA_ID, "test_session_id": original["id"], "test_run_id": run["id"],
              "input_bytes": len(original_bytes), "output_bytes": len(output), "output_dimensions": [5464, 3070],
              "format": generated["image_format"], "elapsed_seconds": round(time.monotonic()-start, 2),
              "parameters_preserved": True, "original_bytes_unchanged": True, "undo_restores_original": True,
              "model_requests": 0}
    out = ROOT / ".test_artifacts" / "post-sliders"
    out.mkdir(exist_ok=True)
    (out / "large-output-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
