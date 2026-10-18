"""Local API acceptance on a small synthetic image; no planner or image-model call."""
import json
import secrets
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

from check_retouch_minimal import fixture

ROOT = Path(__file__).resolve().parents[1]


def main():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                        urllib.request.HTTPCookieProcessor(CookieJar()))

    def request(path, payload=None, raw=None, content_type="application/json"):
        data = json.dumps(payload).encode() if payload is not None else raw
        req = urllib.request.Request("http://127.0.0.1:7301" + path, data=data,
                                     headers={"Content-Type": content_type})
        with opener.open(req, timeout=20) as response:
            return json.loads(response.read())

    request("/api/auth/register", {"username": "slider_smoke_" + secrets.token_hex(5),
                                   "password": secrets.token_urlsafe(24)})
    boundary = "draft" + secrets.token_hex(8)
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="fixture.png"\r\n'
            'Content-Type: image/png\r\n\r\n').encode() + fixture() + f"\r\n--{boundary}--\r\n".encode()
    asset = request("/api/assets", raw=body, content_type=f"multipart/form-data; boundary={boundary}")
    original = request("/api/sessions", {"current_asset_id": asset["id"], "title": "Post sliders synthetic smoke"})
    sid = original["id"]
    prefix = f"/api/sessions/{sid}"
    # Synthetic source identifiers deliberately do not claim ownership of a real analysed photo.
    advice = {"policy_version": "post-sliders-v1", "source_job_id": "job_synthetic_smoke",
        "source_media_id": "media_synthetic_smoke", "source_result_id": "result_synthetic_smoke",
        "params": {"shadows": -.1, "contrast": .08},
        "converted": [
            {"parameter": "Shadows2012", "label": "阴影", "source_value": -10, "source_unit": "参考刻度",
             "target": "shadows", "value": -.1, "approximate": True, "clamped": False, "rule": "v/100", "preview": True},
            {"parameter": "Contrast2012", "label": "对比度", "source_value": 8, "source_unit": "参考刻度",
             "target": "contrast", "value": .08, "approximate": True, "clamped": False, "rule": "v/100", "preview": True}],
        "skipped": [{"parameter": "Dehaze", "reason": "无对应规则，不替代为锐化"}]}
    assert request(prefix)["revision"] == original["revision"]
    params = {"shadows": -.08, "contrast": .06, "layer_id": "base", "expected_revision": original["revision"],
              "advice_context": json.dumps(advice, ensure_ascii=False)}
    run = request(prefix + "/tools", {"tool": "adjust_image", "params": params})["run"]
    deadline = time.monotonic() + 30
    while run["status"] in {"queued", "running"}:
        if time.monotonic() >= deadline:
            raise TimeoutError("Adjustment worker did not finish")
        time.sleep(.3)
        run = request("/api/runs/" + run["id"])
    assert run["status"] == "succeeded", run.get("error")
    current = request(prefix)
    assert current["revision"] > original["revision"]
    assert current["original_asset_id"] == asset["id"] and current["current_asset_id"] != asset["id"]
    history = request(prefix + "/history")
    entry = next(e for e in reversed(history) if e["action"] == "adjust_image")
    assert entry["params"]["shadows"] == -.08 and entry["params"]["contrast"] == .06
    assert entry["params"]["brightness"] == entry["params"]["sharpness"] == 0
    assert json.loads(entry["params"]["advice_context"]) == advice
    restored = request(prefix + "/undo", {})
    assert restored["current_asset_id"] == asset["id"]
    report = {"status": "passed", "session_id": sid, "run_id": run["id"],
        "scope": "synthetic 64x48 fixture through local API/worker/history/undo; not browser or photo-quality evaluation",
        "model_requests": 0, "original_preserved": True, "manual_values_saved": True,
        "provenance_and_skips_saved": True, "undo_restores_original": True}
    out = ROOT / ".test_artifacts" / "post-sliders"
    out.mkdir(exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
