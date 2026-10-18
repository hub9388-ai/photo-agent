"""Local HTTP portrait guard acceptance. No edit is confirmed; no model request."""
import json
import secrets
import time
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

from check_retouch_minimal import fixture

ROOT = Path(__file__).resolve().parents[1]


def main():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                        urllib.request.HTTPCookieProcessor(CookieJar()))
    log = []

    def request(path, payload=None, raw=None, content_type="application/json"):
        data = json.dumps(payload).encode() if payload is not None else raw
        req = urllib.request.Request("http://127.0.0.1:7301" + path, data=data,
                                     headers={"Content-Type": content_type})
        with opener.open(req, timeout=20) as response:
            value = response.read()
            log.append({"path": path, "http_status": response.status})
            return json.loads(value) if value else None

    request("/api/auth/register", {"username": "portrait_guard_" + secrets.token_hex(5),
                                   "password": secrets.token_urlsafe(24)})
    boundary = "guard" + secrets.token_hex(8)
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="guard.png"\r\n'
            'Content-Type: image/png\r\n\r\n').encode() + fixture() + f"\r\n--{boundary}--\r\n".encode()
    asset = request("/api/assets", raw=body, content_type=f"multipart/form-data; boundary={boundary}")
    session = request("/api/sessions", {"current_asset_id": asset["id"], "title": "Portrait guard smoke"})
    sid = session["id"]
    prefix = f"/api/sessions/{sid}"
    missing = request(prefix + "/messages", {"text": "请让人物自然瘦一些"})
    assert missing["status"] == "failed" and missing["steps"] == [] and "笔刷" in missing["error"]
    run = request(prefix + "/tools", {"tool": "split_layers", "params": {}})["run"]
    deadline = time.monotonic() + 20
    while run["status"] in {"queued", "running"}:
        if time.monotonic() >= deadline:
            raise TimeoutError("Split guard worker did not finish")
        time.sleep(0.2)
        run = request("/api/runs/" + run["id"])
    assert run["status"] == "failed" and "拆层" in run["error"]
    request(prefix + "/selection", {"revision": session["revision"], "radius": 0.01,
        "strokes": [[{"x": 0.4, "y": 0.4}, {"x": 0.6, "y": 0.4},
                     {"x": 0.6, "y": 0.6}, {"x": 0.4, "y": 0.6}]]})
    turn = request(prefix + "/messages", {"text": "请轻微瘦腰，保留脸部和衣服"})
    assert turn["status"] == "queued" and len(turn["steps"]) == 1
    assert turn["steps"][0]["tool"] == "replace_region"
    assert turn["steps"][0]["status"] == "waiting" and turn["steps"][0]["run_id"] is None
    canceled = request(prefix + f"/messages/{turn['id']}/cancel", {})
    assert canceled["status"] == "canceled"
    current = request(prefix)
    assert current["revision"] == session["revision"]
    assert current["current_asset_id"] == current["original_asset_id"] == asset["id"]
    report = {"status": "passed", "session_id": sid, "http_steps": log,
              "missing_selection_blocked": True, "simplified_split_blocked": True,
              "selected_body_plan_waits_for_confirmation": True, "test_plan_canceled": True,
              "original_and_revision_unchanged": True,
              "scope": "local API guards and waiting plan only; no model or portrait quality evaluation"}
    out = ROOT / ".test_artifacts/portrait-guards"
    out.mkdir(exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
