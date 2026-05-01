from __future__ import annotations

import copy
import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from photo_runtime import resolve_env_value


PROFILE_SCHEMA_VERSION = 2
ASSET_INDEX_SCHEMA_VERSION = 2
ASSET_INDEX_CACHE_LIMIT = 60
APP_DATA_DIR_NAME = "photo_agent"


def atomic_write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.stem}_",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    temp_path = Path(temp_name)

    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        return path
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def resolve_app_data_dir() -> Path:
    override = resolve_env_value("PHOTO_AGENT_DATA_DIR")
    if override:
        return Path(override)

    if os.name == "nt":
        appdata = os.getenv("APPDATA", "").strip()
        if appdata:
            return Path(appdata) / APP_DATA_DIR_NAME

    return Path.home() / ".photo_agent"


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve(strict=False) == right.resolve(strict=False)
    except OSError:
        return str(left) == str(right)


def migrate_legacy_file(target: Path, legacy_path: str | Path | None) -> Path:
    if legacy_path is None:
        return target

    legacy = Path(legacy_path)
    if not legacy.exists() or _same_path(target, legacy):
        return target

    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(legacy, target)
        except OSError:
            return target
    return target


def migrate_legacy_directory(target_dir: Path, legacy_dir: str | Path | None, *, pattern: str = "*") -> Path:
    if legacy_dir is None:
        return target_dir

    legacy = Path(legacy_dir)
    if not legacy.exists() or _same_path(target_dir, legacy):
        return target_dir

    target_dir.mkdir(parents=True, exist_ok=True)
    for source_path in legacy.glob(pattern):
        if not source_path.is_file():
            continue
        target_path = target_dir / source_path.name
        if target_path.exists():
            continue
        try:
            shutil.copy2(source_path, target_path)
        except OSError:
            continue
    return target_dir


def resolve_profile_path(legacy_path: str | Path | None = None) -> Path:
    target = resolve_app_data_dir() / "user_profile.json"
    return migrate_legacy_file(target, legacy_path)


def resolve_asset_index_dir(legacy_dir: str | Path | None = None) -> Path:
    target = resolve_app_data_dir() / "asset_indexes"
    return migrate_legacy_directory(target, legacy_dir, pattern="*.json")


def resolve_trace_log_dir(legacy_dir: str | Path | None = None, *, dir_name: str = "runtime_logs") -> Path:
    target = resolve_app_data_dir() / dir_name
    return migrate_legacy_directory(target, legacy_dir, pattern="*.jsonl")


def read_json(path: str | Path) -> Any | None:
    json_path = Path(path)
    if not json_path.exists():
        return None
    try:
        with open(json_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def cleanup_json_cache(directory: Path, *, pattern: str = "*.json", keep: int = ASSET_INDEX_CACHE_LIMIT) -> None:
    if keep <= 0 or not directory.exists():
        return

    files = sorted(
        directory.glob(pattern),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for stale_file in files[keep:]:
        try:
            stale_file.unlink()
        except OSError:
            continue


def migrate_profile_payload(payload: dict | None, defaults: dict) -> dict:
    if not isinstance(payload, dict):
        return dict(defaults)

    if isinstance(payload.get("profile"), dict):
        stored_profile = payload["profile"]
    else:
        stored_profile = payload

    return {**defaults, **stored_profile}


def build_profile_document(profile: dict) -> dict:
    return {
        "_schema_version": PROFILE_SCHEMA_VERSION,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "profile": dict(profile),
    }


def _rehydrate_asset_paths(index: dict) -> dict:
    project_root = str(index.get("project_root", "")).strip()
    if not project_root:
        return index

    root_path = Path(project_root)
    for asset in index.get("assets", []):
        if asset.get("absolute_path"):
            continue
        relative_path = str(asset.get("relative_path", "")).strip()
        file_name = str(asset.get("file_name", "")).strip()
        if relative_path:
            asset["absolute_path"] = str(root_path / relative_path)
        elif file_name:
            asset["absolute_path"] = str(root_path / file_name)
    return index


def migrate_asset_index_payload(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return None

    if isinstance(payload.get("index"), dict):
        stored_index = payload["index"]
    else:
        stored_index = payload

    if not isinstance(stored_index, dict):
        return None

    migrated = copy.deepcopy(stored_index)
    migrated.setdefault("scene_groups", [])
    migrated.setdefault("stats", {})
    migrated.setdefault("suggestions", {})
    migrated.setdefault("duplicate_groups", [])
    migrated.setdefault("highlight_ids", [])
    migrated.setdefault("reject_ids", [])
    migrated.setdefault("assets", [])
    return _rehydrate_asset_paths(migrated)


def build_asset_index_document(index: dict) -> dict:
    stored_index = copy.deepcopy(index)
    for asset in stored_index.get("assets", []):
        asset.pop("absolute_path", None)

    return {
        "_schema_version": ASSET_INDEX_SCHEMA_VERSION,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "index": stored_index,
    }
