"""Verify upstream pixels separately from its real HTTP API. No model calls.

core: executes upstream Pillow functions, NOT the HTTP workflow.
api: creates a disposable local test account/assets/session; needs real services.
Credentials and cookies remain in memory. Outputs go to ignored test artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import secrets
import socket
import time
import urllib.error
import urllib.request
import zipfile
from http.cookiejar import CookieJar
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "integrations/ai-retouch-agent/backend/app/edits/pixels.py"


def fixture() -> bytes:
    # Opaque, unclipped colors allow exact checks after canvas flattening.
    image = Image.new("RGBA", (64, 48))
    image.putdata([(40 + x, 50 + y, 80, 255) for y in range(48) for x in range(64)])
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def check_pixels(data: bytes, original: bytes) -> dict:
    with Image.open(io.BytesIO(data)) as output, Image.open(io.BytesIO(original)) as source:
        actual = output.convert("RGBA")
        expected = Image.new("RGBA", source.size)
        source_rgba = source.convert("RGBA")
        expected.putdata([
            (int(r * 1.2), int(g * 1.2), int(b * 1.2), a)
            for y in range(source.height) for x in range(source.width)
            for r, g, b, a in [source_rgba.getpixel((x, y))]
        ])
        if actual.size != source.size:
            raise ValueError("Output dimensions changed")
        extrema = ImageChops.difference(actual, expected).getextrema()
        if any(high != 0 for _, high in extrema):
            raise ValueError("Output differs from expected brightness multiplier 1.2")
        return {"size": list(actual.size), "exact_pixels_match": True}


def core(out: Path, report: dict) -> None:
    spec = importlib.util.spec_from_file_location("upstream_pixels_smoke", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = fixture()
    (out / "input.png").write_bytes(original)
    adjusted = module.adjust(original, brightness=0.2)
    (out / "brightened.png").write_bytes(adjusted)
    report["checks"] = check_pixels(adjusted, original)
    neutral = module.adjust(original, brightness=0)
    black = module.adjust(original, brightness=-1)
    with Image.open(io.BytesIO(original)) as a, Image.open(io.BytesIO(neutral)) as b:
        if a.convert("RGBA").tobytes() != b.convert("RGBA").tobytes():
            raise ValueError("Neutral edit changed pixels")
    with Image.open(io.BytesIO(black)) as image:
        if image.convert("RGB").getbbox() is not None:
            raise ValueError("brightness=-1 did not produce black")
    encoded = module.encode(adjusted, "jpeg")
    (out / "brightened.jpg").write_bytes(encoded)
    with Image.open(io.BytesIO(encoded)) as image:
        if image.format != "JPEG" or image.size != (64, 48):
            raise ValueError("JPEG encoding failed")
    report["checks"].update(neutral_pixels_unchanged=True, negative_boundary_black=True,
                            jpeg_encoding=True)
    report["scope"] = "upstream pixel functions only; no HTTP upload/session/queue/export ZIP"


def api(out: Path, report: dict, *, dialogue: bool = False, planner_failure: bool = False) -> None:
    # Fixed loopback: never send the disposable account/password to a remote service.
    base = "http://127.0.0.1:7301" if dialogue else "http://127.0.0.1:7302"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                        urllib.request.HTTPCookieProcessor(CookieJar()))

    def request(path: str, payload: dict | None = None, *, raw: bytes | None = None,
                content_type: str = "application/json", timeout: int = 15) -> bytes:
        report["stage"] = path
        data = json.dumps(payload).encode() if payload is not None else raw
        req = urllib.request.Request(base + path, data=data,
                                     headers={"Content-Type": content_type})
        started = time.monotonic()
        with opener.open(req, timeout=timeout) as response:
            result = response.read()
            report.setdefault("http_steps", []).append({
                "method": req.get_method(), "path": path, "status": response.status,
                "elapsed_ms": round((time.monotonic() - started) * 1000),
            })
            return result

    health = json.loads(request("/api/health"))
    report["models"] = health.get("models")
    if any(health.get(key) != "ok" for key in ("api", "database", "storage")):
        raise ValueError("API/database/storage health check failed")
    user = "smoke_" + secrets.token_hex(6)
    account = json.loads(request("/api/auth/register", {
        "username": user, "password": secrets.token_urlsafe(24),
    }))
    report["test_user_id"] = account["id"]
    original = fixture()
    (out / "input.png").write_bytes(original)
    boundary = "photoai" + secrets.token_hex(16)
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
            f"filename=\"brightness-smoke.png\"\r\nContent-Type: image/png\r\n\r\n").encode()
    body += original + f"\r\n--{boundary}--\r\n".encode()
    asset = json.loads(request("/api/assets", raw=body,
                              content_type=f"multipart/form-data; boundary={boundary}"))
    session = json.loads(request("/api/sessions", {
        "current_asset_id": asset["id"], "title": "PhotoAI brightness smoke",
    }))
    sid = session["id"]
    report["session_id"] = sid
    if planner_failure:
        turn = json.loads(request(f"/api/sessions/{sid}/messages", {
            "text": "只解释摄影中的曝光是什么意思，不修改图片，不调用任何工具。",
        }, timeout=60))
        history = json.loads(request(f"/api/sessions/{sid}/messages"))
        if turn["steps"] or turn["status"] not in {"failed", "succeeded"}:
            raise ValueError("Unexpected tools or unfinished plan; inspect test session")
        if not any(item["id"] == turn["id"] for item in history):
            raise ValueError("Conversation result was not persisted")
        if turn["status"] == "failed" and not turn.get("error"):
            raise ValueError("Failed turn has no user-facing error")
        report.update(turn_id=turn["id"], turn_status=turn["status"],
                      error=turn.get("error"), persisted=True, tools_submitted=0,
                      scope="one real text planning request via frontend proxy; no image tools")
        return
    if dialogue:
        turn = json.loads(request(f"/api/sessions/{sid}/messages", {
            "text": "只将整张照片的亮度提高20%，只用调色工具，其他保持不变，不要生成新画面。",
        }, timeout=60))
        report["turn_id"] = turn["id"]
        report["planned_steps"] = turn["steps"]
        steps = turn["steps"]
        if len(steps) != 1 or steps[0]["tool"] != "adjust_image" or not steps[0]["run_id"]:
            raise ValueError("Unexpected dialogue plan; inspect the recorded test session")
        run = json.loads(request(f"/api/runs/{steps[0]['run_id']}"))
    else:
        run = json.loads(request(f"/api/sessions/{sid}/tools", {
            "tool": "adjust_image", "params": {"brightness": 0.2},
        }))["run"]
    report["run_id"] = run["id"]
    deadline = time.monotonic() + 60
    while run["status"] not in {"succeeded", "failed", "canceled"}:
        if time.monotonic() >= deadline:
            raise TimeoutError("Tool did not finish in 60 seconds; inspect Redis and worker")
        time.sleep(0.5)
        run = json.loads(request(f"/api/runs/{run['id']}"))
    if run["status"] != "succeeded":
        raise ValueError("Upstream adjust_image task failed; inspect local worker logs")
    archive = request(f"/api/sessions/{sid}/exports", {"asset_ids": []})
    (out / "export.zip").write_bytes(archive)
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        manifest = json.loads(zipped.read("manifest.json"))
        if str(manifest["session_id"]) != sid or len(manifest["items"]) != 1:
            raise ValueError("Unexpected export manifest")
        data = zipped.read(manifest["items"][0]["file"])
    report["checks"] = check_pixels(data, original)
    (out / "exported.png").write_bytes(data)
    report["scope"] = "real dialogue via frontend proxy/planner/Redis/Pillow/export ZIP" if dialogue else "real HTTP account/upload/session/Redis tool/export ZIP"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("core", "api", "dialogue", "planner-error"))
    args = parser.parse_args()
    out = ROOT / ".test_artifacts/retouch-minimal" / args.mode
    out.mkdir(parents=True, exist_ok=True)
    report = {"mode": args.mode, "status": "failed", "stage": "pixel-functions"}
    started = time.monotonic()
    try:
        report["source_sha256"] = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
        if args.mode == "core":
            core(out, report)
        else:
            api(out, report, dialogue=args.mode in {"dialogue", "planner-error"},
                planner_failure=args.mode == "planner-error")
        report["status"] = "passed"
    except urllib.error.HTTPError as exc:
        report["error"] = f"HTTP {exc.code}; inspect upstream logs (response body omitted)"
    except (urllib.error.URLError, ConnectionError, socket.timeout) as exc:
        report["status"] = "blocked"
        report["error"] = f"Local API connection unavailable ({type(exc).__name__})"
    except Exception as exc:
        # Do not persist response bodies, cookies or environment values.
        report["error"] = f"{type(exc).__name__}: {exc}" if isinstance(exc, (ValueError, TimeoutError)) else type(exc).__name__
    report["elapsed_ms"] = round((time.monotonic() - started) * 1000)
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
