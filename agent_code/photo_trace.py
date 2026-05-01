from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from photo_runtime import resolve_env_value
from photo_storage import resolve_trace_log_dir as resolve_storage_trace_log_dir


TRACE_LOG_DIR_NAME = "runtime_logs"
TRACE_FILE_PREFIX = "photo_trace"
USER_INPUT_SUMMARY_LIMIT = 300
USER_INPUT_TRACE_KEYS = {"user_input", "user_text", "input_text"}
SENSITIVE_TRACE_KEY_PARTS = ("api_key", "auth_token", "token", "base64", "data")


def _normalize_trace_flag(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return True
    return normalized not in {"0", "false", "no", "off"}


def is_trace_enabled() -> bool:
    return _normalize_trace_flag(resolve_env_value("PHOTO_AGENT_TRACE_ENABLED"))


def resolve_trace_log_dir() -> Path:
    override = resolve_env_value("PHOTO_AGENT_TRACE_DIR")
    if override:
        return Path(override)
    legacy_dir = Path(__file__).resolve().parent / TRACE_LOG_DIR_NAME
    return resolve_storage_trace_log_dir(legacy_dir, dir_name=TRACE_LOG_DIR_NAME)


def resolve_trace_log_path() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d")
    return resolve_trace_log_dir() / f"{TRACE_FILE_PREFIX}_{timestamp}.jsonl"


def _summarize_user_input(value: Any, limit: int = USER_INPUT_SUMMARY_LIMIT) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _is_sensitive_trace_key(key: str) -> bool:
    normalized = key.lower()
    return any(part in normalized for part in SENSITIVE_TRACE_KEY_PARTS)


def _sanitize_trace_value(value: Any, depth: int = 0, key_hint: str = "") -> Any:
    if depth >= 4:
        return str(value)

    if key_hint in USER_INPUT_TRACE_KEYS:
        return _summarize_user_input(value)

    if key_hint and _is_sensitive_trace_key(key_hint):
        return "<redacted>"

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in list(value.items())[:40]:
            key_text = str(key)
            sanitized[key_text] = _sanitize_trace_value(item, depth + 1, key_text)
        return sanitized

    if isinstance(value, (list, tuple, set)):
        return [_sanitize_trace_value(item, depth + 1) for item in list(value)[:40]]

    return str(value)


def trace_event(event_type: str, **payload: Any) -> Path | None:
    if not is_trace_enabled():
        return None

    try:
        path = resolve_trace_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        user_input_summary = _extract_user_input_summary(payload)
        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "event": str(event_type).strip() or "unknown",
            "payload": _sanitize_trace_value(payload),
        }
        if user_input_summary:
            record["user_input_summary"] = user_input_summary
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")
        return path
    except OSError:
        return None


def _extract_user_input_summary(payload: dict[str, Any]) -> str:
    for key in USER_INPUT_TRACE_KEYS:
        if key in payload:
            return _summarize_user_input(payload[key])
    return ""
