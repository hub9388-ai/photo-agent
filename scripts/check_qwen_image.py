"""Inspect/configure Alibaba credentials safely, then submit at most one image edit.

Never prints API keys, raw responses, signed image URLs, or request image data.
The fixed attempt marker prevents accidental duplicate generation submissions.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".test_artifacts/qwen-image-single-test"
PRIVATE = ROOT / ".test_artifacts/retouch-service.env"
MODEL = "qwen-image-2.1-pro"
SOURCE = ROOT / "media/originals/media_5422d0e6fb714a649736a69ffa74db88.jpg"
PROMPT = (
    "编辑这张猫咪照片：让猫咪的脸颊和身体略微更圆润可爱，眼神带一点好奇和迷惑。"
    "保持同一只三花猫的毛色花纹、坐姿、四肢和尾巴完整，保持街景背景与竖幅构图，"
    "保持真实摄影质感。只做自然适度的修改，不增加其他动物，不添加文字。"
)


def records(path: Path) -> list[tuple[int, str, str]]:
    result = []
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        match = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", line)
        if match:
            value = match[2].strip().strip('"').strip("'").replace("\\:", ":")
            result.append((number, match[1], value))
    return result


def official_origin(raw: str) -> str:
    url = urlsplit(raw)
    host = url.hostname or ""
    allowed = host == "dashscope.aliyuncs.com" or bool(
        re.fullmatch(r"[a-z0-9-]+\.cn-beijing\.maas\.aliyuncs\.com", host)
    )
    if not allowed or url.scheme != "https" or url.username or url.password or url.query or url.fragment or url.port:
        raise ValueError("Expected an official Beijing Alibaba HTTPS endpoint")
    if url.path.rstrip("/") not in {"", "/compatible-mode/v1", "/api/v1"}:
        raise ValueError("Unrecognized Alibaba base URL path")
    return f"https://{host}"


def resolve() -> tuple[str, str, dict]:
    rows = records(ROOT / "model.env")
    keys = [(line, name, value) for line, name, value in rows
            if name in {"DASHSCOPE_API_KEY", "QWEN_API_KEY", "BAILIAN_API_KEY"} and value]
    urls = [(line, name, value) for line, name, value in rows
            if name in {"DASHSCOPE_BASE_URL", "QWEN_BASE_URL", "BAILIAN_BASE_URL"} and value]
    if len({value for _, _, value in keys}) == 1:
        key_line, key_name, key = keys[-1]
        base = official_origin(urls[-1][2]) if urls else "https://dashscope.aliyuncs.com"
    elif keys:
        raise ValueError("Conflicting explicit Alibaba keys; resolve locally before testing")
    else:
        # Legacy file repeats ANTHROPIC_* names for different providers. Pair each
        # URL only with the immediately preceding credential in that same group.
        candidates = []
        for index, (line, name, value) in enumerate(rows):
            if name != "ANTHROPIC_BASE_URL":
                continue
            try:
                origin = official_origin(value)
            except ValueError:
                continue
            if index and rows[index - 1][1] in {"ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY"}:
                previous = rows[index - 1]
                if previous[2] and line - previous[0] <= 3:
                    candidates.append((previous, origin))
        if len(candidates) != 1:
            raise ValueError("Need one unambiguous Alibaba credential/official URL pair")
        (key_line, key_name, key), base = candidates[0]
    if not re.fullmatch(r"sk-[A-Za-z0-9_-]+", key):
        raise ValueError("Alibaba key format invalid; inspect the private file locally")
    return key, base, {"key_source_name": key_name, "key_source_line": key_line,
                       "key_present": True, "base_origin": base, "model": MODEL}


def configure(key: str, base: str, *, activate: bool = False) -> None:
    if not PRIVATE.exists():
        raise ValueError("Run retouch-service.ps1 -Action Prepare first")
    updates = {"DASHSCOPE_API_KEY": key, "DASHSCOPE_BASE_URL": base, "IMAGE_EDIT_MODEL": MODEL}
    if activate:
        updates.update(IMAGE_PROVIDER="dashscope", PLANNER_MODEL="qwen-plus", TEXT_TO_IMAGE_MODEL=MODEL)
    lines = PRIVATE.read_text(encoding="utf-8-sig").splitlines()
    seen = set()
    result = []
    for line in lines:
        name = line.partition("=")[0].strip()
        if name in updates:
            if name not in seen:
                result.append(f"{name}={updates[name]}")
                seen.add(name)
        else:
            result.append(line)
    result.extend(f"{name}={value}" for name, value in updates.items() if name not in seen)
    PRIVATE.write_text("\n".join(result) + "\n", encoding="utf-8")


async def preflight(key: str, base: str) -> dict:
    # Model listing performs no image generation. Do not persist the body.
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(base + "/compatible-mode/v1/models",
                                    headers={"Authorization": f"Bearer {key}"})
    body = response.json()
    result = {"http_status": response.status_code}
    if response.status_code != 200:
        result["status"] = "failed"
        error = body.get("error", body)
        result["error_code"] = str(error.get("code", "unknown"))[:80]
    else:
        result.update(status="passed", target_in_model_list=any(
            item.get("id") == MODEL for item in body.get("data", [])
        ))
    return result


async def run(key: str, base: str, report: dict) -> None:
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    with Image.open(SOURCE) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, "PNG")  # Strip EXIF/GPS and match the adapter's PNG MIME.
        input_bytes = buffer.getvalue()
    (OUT / "input.png").write_bytes(input_bytes)
    report.update(input_source=str(SOURCE.relative_to(ROOT)), input_sha256=source_hash,
                  submitted_size=list(image.size), prompt=PROMPT, image_count=1)
    os.environ.update(DASHSCOPE_API_KEY=key, DASHSCOPE_BASE_URL=base, IMAGE_EDIT_MODEL=MODEL)
    sys.path.insert(0, str(ROOT / "integrations/ai-retouch-agent/backend"))
    from app.config import get_settings
    from app.providers.base import EditRequest, ProviderError
    from app.providers.dashscope import DashScopeImageProvider, _EDIT_PATH
    get_settings.cache_clear()
    provider = DashScopeImageProvider()
    request = EditRequest(prompt=PROMPT, image=input_bytes, count=1, width=768, height=1024)
    payload = provider._edit_payload(request)
    if payload["model"] != MODEL or payload["parameters"]["n"] != 1:
        raise ValueError("Unexpected provider request")
    report["request_path"] = _EDIT_PATH
    report["parameters"] = payload["parameters"]
    # Persist before any POST. Never remove/retry this marker automatically.
    marker = OUT / "attempt.json"
    try:
        with marker.open("x", encoding="utf-8") as stream:
            json.dump({"started_at": datetime.now(timezone.utc).isoformat(),
                       "model": MODEL, "count": 1}, stream)
    except FileExistsError:
        raise ValueError("An image attempt is already recorded; no duplicate POST submitted") from None
    report.update(status="submitted", post_attempts=1)
    started = time.monotonic()
    try:
        # Same payload/path/parser/downloader as the current upstream adapter.
        response = await provider._client.post(_EDIT_PATH, json=payload, timeout=180)
        report["http_status"] = response.status_code
        try:
            body = response.json()
        except ValueError:
            report.update(status="failed", error_code="NonJSONResponse")
            return
        report["request_id"] = body.get("request_id")
        report["usage"] = body.get("usage")
        if response.status_code != 200 or "code" in body:
            report.update(status="failed", error_code=body.get("code", "HTTPError"))
            return
        from app.providers.dashscope import _extract_urls
        urls = _extract_urls(provider._parse(response).get("output", {}))
        if len(urls) != 1:
            raise ValueError("Unexpected generated image count")
        edited = await provider._download(urls[0])
        with Image.open(io.BytesIO(edited)) as output:
            output.load()
            report["output_size"] = list(output.size)
            report["output_format"] = output.format
            different = output.convert("RGB").size != image.size or output.convert("RGB").tobytes() != image.tobytes()
        (OUT / "edited.png").write_bytes(edited)
        report.update(status="passed", output_sha256=hashlib.sha256(edited).hexdigest(),
                      differs_from_input=different, quality_review="pending")
    finally:
        report["elapsed_ms"] = round((time.monotonic() - started) * 1000)
        await provider._client.aclose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("inspect", "configure", "activate", "preflight", "run"))
    action = parser.parse_args().action
    if action == "run" and (OUT / "attempt.json").exists():
        print(json.dumps({"status": "blocked", "error": "An attempt already exists; no POST sent and original report preserved"}))
        return 1
    report = {"action": action, "status": "failed"}
    try:
        key, base, metadata = resolve()
        report.update(metadata)
        if action in {"configure", "activate"}:
            configure(key, base, activate=action == "activate")
            report.update(status="configured", image_provider_activation="dashscope" if action == "activate" else "unchanged")
        elif action == "preflight":
            report.update(asyncio.run(preflight(key, base)))
        elif action == "run":
            OUT.mkdir(parents=True, exist_ok=True)
            asyncio.run(run(key, base, report))
        else:
            report["status"] = "inspected"
    except (ValueError, FileNotFoundError) as exc:
        report["error"] = str(exc)
    except Exception as exc:
        report["error_type"] = type(exc).__name__  # Never print raw HTTP exceptions/headers.
    if action in {"preflight", "run"}:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"{action}-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["status"] in {"inspected", "configured", "passed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
