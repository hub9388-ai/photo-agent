"""
摄影全栈 Agent - V4 素材管理模块
================================
功能：
  1. 导入项目文件夹或一批原片，建立结构化索引
  2. 读取基础元数据与视觉特征，完成场景分组和连拍归并
  3. 识别废片候选、重复片与精选候选
  4. 生成标签、命名与归档建议
  5. 支持自然语言搜索，并为后期辅助 / 学习教练准备流转入口
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import sys
import warnings
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

import anthropic
from PIL import ExifTags, Image, ImageFilter, ImageStat

from photo_events import EventSink, ensure_event_sink
from photo_utils import normalize_string_list
from photo_storage import (
    ASSET_INDEX_CACHE_LIMIT,
    atomic_write_json,
    build_asset_index_document,
    cleanup_json_cache,
    migrate_asset_index_payload,
    read_json,
    resolve_app_data_dir,
    resolve_asset_index_dir,
)
from photo_v1 import (
    MODEL,
    DEFAULT_PROFILE,
    DEFAULT_SESSION_STATE,
    RAW_EXTS,
    SUPPORTED_IMAGE_EXTS,
    SUPPORTED_INPUT_EXTS,
    build_media_signature,
    compact_note_text,
    extract_json_object,
    find_sidecar_preview,
    has_context_carryover_intent,
    init_profile_interactive,
    is_profile_initialized,
    load_profile,
    looks_like_local_media_reference,
    maybe_print_media_input_hint,
    parse_media_request,
    print_input_format_tips,
    profile_summary,
    save_profile,
)

SAFE_MAX_IMAGE_PIXELS = 400_000_000
SAFE_PREVIEW_MAX_EDGE = 4096
VISUAL_ANALYSIS_MAX_EDGE = 256

Image.MAX_IMAGE_PIXELS = SAFE_MAX_IMAGE_PIXELS

LEGACY_ASSET_INDEX_DIR = Path(__file__).parent / "asset_indexes"
ASSET_INDEX_DIR = resolve_app_data_dir() / "asset_indexes"
SCENE_TIME_GAP_MINUTES = 30
BURST_TIME_GAP_SECONDS = 3
NEAR_DUPLICATE_HASH_DISTANCE = 6
SEARCH_RESULT_LIMIT = 30
MAX_HANDOFF_ITEMS = 20

EXIF_TAGS = ExifTags.TAGS

DEFAULT_ASSET_PROFILE_FIELDS = {
    "culling_preference": "balanced",
    "naming_rule": "",
    "folder_rule": "",
    "tag_taxonomy": "",
}

DEFAULT_ASSET_SESSION_STATE = {
    **DEFAULT_SESSION_STATE,
    "current_project_root": "",
    "current_project_name": "",
    "current_focus_paths": [],
    "last_index_cache": "",
    "last_search_query": "",
    "last_search_filters": {},
    "last_search_result_paths": [],
    "last_highlight_ids": [],
    "last_reject_ids": [],
    "last_duplicate_groups": [],
    "current_culling_preference": "balanced",
    "last_handoff_destination": "",
    "last_handoff_paths": [],
    "last_handoff_assets": [],
    "last_handoff_note": "",
}

ASSET_TASK_MODE_ALIASES = {
    "show_highlights": "show_grade_b",
}

EXPLICIT_TASK_KEYWORDS = [
    ("prepare_handoff", ("后期辅助", "后期", "送去后期", "学习教练", "复盘", "送去学习")),
    ("show_grade_a", ("典藏", "收藏级", "首选")),
    ("show_grade_b", ("佳片", "精选", "可交付", "最好", "候选")),
    ("show_grade_c", ("留存", "一般", "普通", "保留")),
    ("show_rejects", ("清理", "废片", "不可用", "误触", "删除")),
    ("show_duplicates", ("重复", "相似")),
    ("show_suggestions", ("命名", "标签", "归档")),
]

GRADE_LABELS = {
    "A": "典藏",
    "B": "佳片",
    "C": "留存",
    "Reject": "清理",
}

GRADE_SORT_ORDER = {
    "A": 0,
    "B": 1,
    "C": 2,
    "Reject": 3,
}


def ensure_asset_profile_fields(profile: dict) -> dict:
    merged = {**DEFAULT_PROFILE, **DEFAULT_ASSET_PROFILE_FIELDS, **profile}
    return merged


def asset_state_summary(session_state: dict) -> str:
    parts = []
    if session_state.get("current_project_name"):
        parts.append(f"current project: {session_state['current_project_name']}")
    if session_state.get("current_project_root"):
        parts.append(f"current path: {session_state['current_project_root']}")
    if session_state.get("current_culling_preference"):
        parts.append(f"culling preference: {session_state['current_culling_preference']}")
    if session_state.get("last_search_query"):
        parts.append(f"last search: {session_state['last_search_query']}")
    if session_state.get("current_focus_paths"):
        parts.append(f"focus assets: {len(session_state['current_focus_paths'])}")
    if session_state.get("last_handoff_destination"):
        parts.append(f"last handoff: {session_state['last_handoff_destination']}")
    if not parts:
        return "(no active asset-management context)"
    return " | ".join(parts)

def normalize_culling_preference(text: str) -> str:
    lowered = str(text).strip().lower()
    if not lowered:
        return ""

    mapping = {
        "conservative": "conservative",
        "保守": "conservative",
        "宁可多保留": "conservative",
        "多保留": "conservative",
        "balanced": "balanced",
        "平衡": "balanced",
        "默认": "balanced",
        "aggressive": "aggressive",
        "激进": "aggressive",
        "宁可多过滤": "aggressive",
        "多过滤": "aggressive",
        "严格": "aggressive",
    }
    for key, value in mapping.items():
        if key in lowered:
            return value
    return ""


def format_culling_preference(value: str) -> str:
    mapping = {
        "conservative": "保守",
        "balanced": "平衡",
        "aggressive": "激进",
    }
    return mapping.get(value, value or "平衡")


def format_delivery_grade(value: str) -> str:
    return GRADE_LABELS.get(value, value or "未分级")


def delivery_grade_order(value: str) -> int:
    return GRADE_SORT_ORDER.get(value, len(GRADE_SORT_ORDER))


def sort_assets_for_display(assets: list[dict]) -> list[dict]:
    return sorted(
        assets,
        key=lambda asset: (
            delivery_grade_order(asset.get("delivery_grade", "")),
            -(float(asset.get("quality_score", 0) or 0)),
            str(asset.get("scene_id", "")),
            str(asset.get("relative_path", "")),
        ),
    )


def fallback_asset_intent(user_input: str, has_project_path: bool, has_current_index: bool) -> dict:
    text = user_input.strip()

    if has_project_path:
        task_mode = "import_project"
    elif any(keyword in text for keyword in ("后期辅助", "后期", "送去后期", "学习教练", "复盘", "送去学习")):
        task_mode = "prepare_handoff"
    elif any(keyword in text for keyword in ("典藏", "收藏级", "首选")):
        task_mode = "show_grade_a"
    elif any(keyword in text for keyword in ("佳片", "精选", "可交付", "最好")):
        task_mode = "show_grade_b"
    elif any(keyword in text for keyword in ("留存", "一般", "普通", "保留")):
        task_mode = "show_grade_c"
    elif any(keyword in text for keyword in ("清理", "废片", "不可用", "误触", "删除")):
        task_mode = "show_rejects"
    elif any(keyword in text for keyword in ("找", "搜索", "检索", "上个月", "去年", "傍晚", "海边")):
        task_mode = "search_assets"
    elif any(keyword in text for keyword in ("候选",)):
        task_mode = "show_grade_b"
    elif any(keyword in text for keyword in ("重复", "相似")):
        task_mode = "show_duplicates"
    elif any(keyword in text for keyword in ("命名", "标签", "归档")):
        task_mode = "show_suggestions"
    else:
        task_mode = "search_assets" if has_current_index else "import_project"

    destination = ""
    if "后期" in text:
        destination = "post"
    elif "学习" in text or "复盘" in text:
        destination = "coach"

    return {
        "task_mode": task_mode,
        "user_goal": text,
        "project_name": "",
        "client_name": "",
        "subject_type": "",
        "due_date": "",
        "culling_preference": normalize_culling_preference(text),
        "naming_rule": "",
        "folder_rule": "",
        "tag_taxonomy": "",
        "search_query": text if task_mode == "search_assets" else "",
        "destination": destination,
        "needs_project_path": task_mode == "import_project" and not has_project_path,
        "clarification_question": "Please send a project folder or a batch of source photos first.",
    }


def detect_explicit_asset_task_mode(user_input: str) -> str:
    text = str(user_input).strip()
    if not text:
        return ""
    for task_mode, keywords in EXPLICIT_TASK_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return task_mode
    return ""


def normalize_asset_task_mode(task_mode: str, fallback_task_mode: str) -> str:
    normalized = ASSET_TASK_MODE_ALIASES.get(str(task_mode).strip(), str(task_mode).strip())
    allowed = {
        "import_project",
        "search_assets",
        "show_grade_a",
        "show_grade_b",
        "show_grade_c",
        "show_rejects",
        "show_duplicates",
        "show_suggestions",
        "prepare_handoff",
        "asset_chat",
    }
    return normalized if normalized in allowed else fallback_task_mode


def build_asset_intent_prompt(profile: dict, session_state: dict, has_project_path: bool, has_current_index: bool) -> str:
    return f"""You are the intent parser for the asset-management agent. Output JSON only.
Profile summary: {profile_summary(profile)}
Asset session summary: {asset_state_summary(session_state)}
Project path already parsed by outer layer: {"yes" if has_project_path else "no"}
Current index available: {"yes" if has_current_index else "no"}

Task modes:
- import_project: import a folder or batch of source photos and build an index
- search_assets: search indexed assets using natural language
- show_grade_a: show gallery-grade picks
- show_grade_b: show strong deliverable picks
- show_grade_c: show keep-but-not-featured picks
- show_rejects: show reject candidates
- show_duplicates: show duplicate or near-duplicate assets
- show_suggestions: show naming, tagging, and archive suggestions
- prepare_handoff: prepare a handoff to post or coach
- asset_chat: follow-up chat when nothing above matches

Rules:
1. If a project path is already available, prefer import_project unless the user clearly asks for another task.
2. Map conservative / balanced / aggressive language into culling_preference when possible.
3. Map post-processing requests to destination=post.
4. Map learning / review requests to destination=coach.
5. If import_project is required but no path is available, set needs_project_path=true.

Return JSON with this shape:
{{
  "task_mode": "import_project | search_assets | show_grade_a | show_grade_b | show_grade_c | show_rejects | show_duplicates | show_suggestions | prepare_handoff | asset_chat",
  "user_goal": "one-sentence summary",
  "project_name": "",
  "client_name": "",
  "subject_type": "",
  "due_date": "",
  "culling_preference": "conservative | balanced | aggressive | ''",
  "naming_rule": "",
  "folder_rule": "",
  "tag_taxonomy": "",
  "search_query": "",
  "destination": "post | coach | ''",
  "needs_project_path": false,
  "clarification_question": ""
}}
"""
def resolve_asset_intent(
    client: anthropic.Anthropic,
    user_input: str,
    profile: dict,
    session_state: dict,
    has_project_path: bool,
    has_current_index: bool,
) -> dict:
    fallback = fallback_asset_intent(user_input, has_project_path, has_current_index)
    explicit_task_mode = detect_explicit_asset_task_mode(user_input)
    try:
        raw_chunks: list[str] = []
        with client.messages.stream(
            model=MODEL,
            max_tokens=700,
            system=build_asset_intent_prompt(profile, session_state, has_project_path, has_current_index),
            messages=[{"role": "user", "content": user_input.strip() or "Please help manage this asset batch."}],
        ) as stream:
            for chunk in stream.text_stream:
                raw_chunks.append(chunk)
        raw_text = "".join(raw_chunks).strip()
        payload = extract_json_object(raw_text)
    except Exception as e:
        print(f"\n[素材管理] 意图解析失败（{type(e).__name__}: {e}），使用规则兜底。\n")
        return fallback

    intent = {
        "task_mode": normalize_asset_task_mode(
            payload.get("task_mode", "") or fallback["task_mode"],
            fallback["task_mode"],
        ),
        "user_goal": str(payload.get("user_goal", "")).strip() or fallback["user_goal"],
        "project_name": str(payload.get("project_name", "")).strip(),
        "client_name": str(payload.get("client_name", "")).strip(),
        "subject_type": str(payload.get("subject_type", "")).strip(),
        "due_date": str(payload.get("due_date", "")).strip(),
        "culling_preference": normalize_culling_preference(payload.get("culling_preference", "")),
        "naming_rule": str(payload.get("naming_rule", "")).strip(),
        "folder_rule": str(payload.get("folder_rule", "")).strip(),
        "tag_taxonomy": str(payload.get("tag_taxonomy", "")).strip(),
        "search_query": str(payload.get("search_query", "")).strip(),
        "destination": str(payload.get("destination", "")).strip(),
        "needs_project_path": bool(payload.get("needs_project_path", False)),
        "clarification_question": str(payload.get("clarification_question", "")).strip(),
    }

    if explicit_task_mode:
        intent["task_mode"] = normalize_asset_task_mode(explicit_task_mode, intent["task_mode"])

    if not intent["culling_preference"]:
        intent["culling_preference"] = fallback["culling_preference"]
    if not intent["search_query"] and intent["task_mode"] == "search_assets":
        intent["search_query"] = user_input.strip()
    if not intent["destination"]:
        intent["destination"] = fallback["destination"]
    if intent["task_mode"] == "import_project" and not has_project_path and not session_state.get("current_project_root"):
        intent["needs_project_path"] = True
        if not intent["clarification_question"]:
            intent["clarification_question"] = "Please send a project folder or a batch of source photos first."
    return intent


def update_profile_from_asset_intent(profile: dict, intent: dict) -> dict:
    updated = ensure_asset_profile_fields(profile)

    if intent.get("culling_preference"):
        updated["culling_preference"] = intent["culling_preference"]
    if intent.get("naming_rule"):
        updated["naming_rule"] = intent["naming_rule"]
    if intent.get("folder_rule"):
        updated["folder_rule"] = intent["folder_rule"]
    if intent.get("tag_taxonomy"):
        updated["tag_taxonomy"] = intent["tag_taxonomy"]

    save_profile(updated)
    return updated


def project_cache_path(project_root: Path) -> Path:
    asset_index_dir = resolve_asset_index_dir(LEGACY_ASSET_INDEX_DIR)
    asset_index_dir.mkdir(parents=True, exist_ok=True)
    try:
        normalized = str(project_root.resolve(strict=False)).lower()
    except OSError:
        normalized = str(project_root).lower()
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]
    safe_name = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", project_root.name).strip("_") or "project"
    return asset_index_dir / f"{safe_name}_{digest}.json"


def asset_relative_path(path: Path, project_root: Path) -> str:
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return path.name


def normalize_asset_cache_key(relative_path: str) -> str:
    return str(relative_path).strip().replace("/", "\\").lower()


def build_incremental_asset_cache(index: dict | None) -> dict[str, dict]:
    cache: dict[str, dict] = {}
    if not isinstance(index, dict):
        return cache

    for asset in index.get("assets", []):
        cache_key = normalize_asset_cache_key(asset.get("relative_path", ""))
        if not cache_key:
            continue
        cache[cache_key] = asset
    return cache


def build_asset_cache_signature(path: Path, project_root: Path) -> dict[str, str | int]:
    relative_path = asset_relative_path(path, project_root)
    try:
        stat = path.stat()
    except OSError:
        return {
            "relative_path": relative_path,
            "cache_key": normalize_asset_cache_key(relative_path),
            "file_size_bytes": 0,
            "modified_at": "",
        }

    return {
        "relative_path": relative_path,
        "cache_key": normalize_asset_cache_key(relative_path),
        "file_size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }


def can_reuse_cached_asset(cached_asset: dict | None, signature: dict[str, str | int]) -> bool:
    if not isinstance(cached_asset, dict):
        return False
    return (
        str(cached_asset.get("modified_at", "")) == str(signature.get("modified_at", ""))
        and int(cached_asset.get("file_size_bytes", 0) or 0) == int(signature.get("file_size_bytes", 0) or 0)
    )


def reuse_cached_asset_record(
    cached_asset: dict,
    path: Path,
    project_root: Path,
    intent: dict,
    project_name: str,
) -> dict:
    reused = copy.deepcopy(cached_asset)
    relative_path = asset_relative_path(path, project_root)

    try:
        resolved_path = str(path.resolve(strict=False))
    except OSError:
        resolved_path = str(path)

    reused["id"] = ""
    reused["project_name"] = project_name
    reused["absolute_path"] = resolved_path
    reused["relative_path"] = relative_path
    reused["folder_name"] = path.parent.name
    reused["scene_id"] = ""
    reused["burst_id"] = ""
    reused["duplicate_group"] = ""
    reused["duplicate_of"] = ""
    reused["reject_reasons"] = []
    reused["quality_score"] = 0.0
    reused["delivery_grade"] = ""
    reused["is_highlight_candidate"] = False
    reused["is_reject_candidate"] = False
    reused["tags"] = infer_semantic_tags(reused, intent)
    return reused


def choose_index_worker_count(rebuild_count: int) -> int:
    if rebuild_count <= 1:
        return 1
    cpu_count = os.cpu_count() or 4
    return max(2, min(8, cpu_count, rebuild_count))


def collect_asset_paths(paths: list[Path]) -> list[Path]:
    collected: list[Path] = []
    seen: set[str] = set()

    for path in paths:
        if path.is_dir():
            folder_items = sorted(
                p for p in path.rglob("*")
                if p.is_file() and p.suffix.lower() in SUPPORTED_INPUT_EXTS
            )
            raw_stems = {
                str(p.parent / p.stem).lower()
                for p in folder_items
                if p.suffix.lower() in RAW_EXTS
            }
            for item in folder_items:
                item_key = str(item.resolve(strict=False)).lower()
                same_stem_key = str(item.parent / item.stem).lower()
                if (
                    item.suffix.lower() in SUPPORTED_IMAGE_EXTS and
                    same_stem_key in raw_stems
                ):
                    continue
                if item_key in seen:
                    continue
                seen.add(item_key)
                collected.append(item)
        else:
            if path.suffix.lower() not in SUPPORTED_INPUT_EXTS:
                continue
            try:
                key = str(path.resolve(strict=False)).lower()
            except OSError:
                key = str(path).lower()
            if key in seen:
                continue
            seen.add(key)
            collected.append(path)

    return sorted(collected)


def detect_project_root(paths: list[Path]) -> Path:
    if not paths:
        return Path.cwd()

    normalized = [path if path.is_dir() else path.parent for path in paths]
    if len(normalized) == 1:
        return normalized[0]

    parts_list = [path.parts for path in normalized]
    common_parts: list[str] = []
    for group in zip(*parts_list):
        if all(part == group[0] for part in group):
            common_parts.append(group[0])
        else:
            break

    if common_parts:
        return Path(*common_parts)
    return normalized[0]


def infer_project_name(project_root: Path, intent: dict) -> str:
    if intent.get("project_name"):
        return intent["project_name"]

    pieces = [project_root.name]
    if intent.get("client_name"):
        pieces.insert(0, intent["client_name"])
    if intent.get("subject_type"):
        pieces.append(intent["subject_type"])
    return "_".join(piece for piece in pieces if piece).strip("_")


def parse_datetime_text(value: str) -> datetime | None:
    text = str(value).strip()
    if not text:
        return None

    formats = [
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def exif_value_to_float(value) -> float | None:
    if value is None:
        return None
    try:
        if hasattr(value, "numerator") and hasattr(value, "denominator"):
            denominator = value.denominator or 1
            return float(value.numerator) / float(denominator)
        if isinstance(value, tuple) and len(value) == 2:
            denominator = value[1] or 1
            return float(value[0]) / float(denominator)
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def exposure_time_to_text(value) -> str:
    numeric = exif_value_to_float(value)
    if numeric is None or numeric <= 0:
        return ""
    if numeric >= 1:
        return f"{numeric:.1f}s".rstrip("0").rstrip(".")
    denominator = round(1 / numeric)
    if denominator > 0:
        return f"1/{denominator}s"
    return f"{numeric:.4f}s"


def file_sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def average_hash_bitstring(img: Image.Image, hash_size: int = 8) -> str:
    grayscale = img.convert("L").resize((hash_size, hash_size), Image.LANCZOS)
    pixels = list(grayscale.getdata())
    mean = sum(pixels) / len(pixels)
    return "".join("1" if pixel >= mean else "0" for pixel in pixels)


def hash_distance(left: str, right: str) -> int:
    if not left or not right or len(left) != len(right):
        return 999
    return sum(1 for a, b in zip(left, right) if a != b)


def resolve_preview_source(path: Path) -> tuple[Path | None, str]:
    ext = path.suffix.lower()
    if ext in SUPPORTED_IMAGE_EXTS:
        return path, path.name

    if ext in RAW_EXTS:
        preview = find_sidecar_preview(path)
        if preview is not None:
            return preview, preview.name
    return None, ""


def open_metadata_image(path: Path) -> tuple[Image.Image | None, str]:
    preview_path, source_name = resolve_preview_source(path)
    if preview_path is None:
        return None, ""

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            return Image.open(preview_path), source_name
    except (OSError, Image.DecompressionBombError):
        return None, ""


def open_visual_preview_image(path: Path) -> tuple[Image.Image | None, str, str]:
    preview_path, source_name = resolve_preview_source(path)
    if preview_path is None:
        return None, "", "unavailable"

    source_image: Image.Image | None = None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            source_image = Image.open(preview_path)

        width, height = source_image.size
        pixel_count = width * height
        should_downsample = (
            pixel_count > SAFE_MAX_IMAGE_PIXELS
            or max(width, height) > SAFE_PREVIEW_MAX_EDGE
        )

        if should_downsample:
            try:
                source_image.draft("RGB", (SAFE_PREVIEW_MAX_EDGE, SAFE_PREVIEW_MAX_EDGE))
            except (AttributeError, OSError, ValueError):
                pass

        preview = source_image.convert("RGB")
        visual_status = "ok"
        if should_downsample:
            preview.thumbnail((SAFE_PREVIEW_MAX_EDGE, SAFE_PREVIEW_MAX_EDGE), Image.LANCZOS)
            visual_status = "downsampled"
        return preview, source_name, visual_status
    except (MemoryError, OSError, Image.DecompressionBombError):
        fallback_status = "oversized_skipped"
        if source_image is not None:
            try:
                width, height = source_image.size
                if width * height <= SAFE_MAX_IMAGE_PIXELS and max(width, height) <= SAFE_PREVIEW_MAX_EDGE:
                    fallback_status = "error"
            except Exception:
                fallback_status = "error"
        return None, source_name, fallback_status
    finally:
        if source_image is not None:
            source_image.close()


def classify_time_of_day(capture_dt: datetime | None, brightness: float | None) -> str:
    if capture_dt is not None:
        hour = capture_dt.hour
        if 5 <= hour < 8:
            return "清晨"
        if 8 <= hour < 16:
            return "白天"
        if 16 <= hour < 19:
            return "傍晚"
        return "夜间"

    if brightness is None:
        return ""
    if brightness < 40:
        return "夜间"
    if brightness < 95:
        return "傍晚"
    return "白天"


def infer_semantic_tags(asset: dict, intent: dict) -> list[str]:
    text_blob = " ".join(
        str(part)
        for part in [
            asset.get("relative_path", ""),
            asset.get("folder_name", ""),
            intent.get("project_name", ""),
            intent.get("subject_type", ""),
            intent.get("client_name", ""),
        ]
    ).lower()

    tag_rules = {
        "beach": ["beach", "coast", "sea", "shore", "sand"],
        "portrait": ["portrait", "couple", "wedding", "bride", "model", "girl", "boy"],
        "street": ["street", "citywalk", "urban"],
        "landscape": ["landscape", "mountain", "lake", "sunset"],
        "night": ["night", "citynight", "concert", "stage"],
        "indoor": ["indoor", "studio", "cafe"],
        "travel": ["travel", "trip"],
    }

    tags: set[str] = set()
    for tag, keywords in tag_rules.items():
        if any(keyword in text_blob for keyword in keywords):
            tags.add(tag)

    if asset.get("time_of_day"):
        tags.add(asset["time_of_day"])
    if asset.get("orientation"):
        tags.add(asset["orientation"])
    if asset.get("warmth_tag"):
        tags.add(asset["warmth_tag"])
    if intent.get("client_name"):
        tags.add(intent["client_name"])
    if intent.get("subject_type"):
        tags.add(intent["subject_type"])

    return sorted(tags)
def read_asset_metadata(path: Path) -> dict:
    stat = path.stat()
    meta = {
        "file_name": path.name,
        "extension": path.suffix.lower(),
        "file_size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "capture_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "capture_source": "file_mtime",
        "camera_model": "",
        "lens_model": "",
        "iso": "",
        "aperture": "",
        "shutter": "",
        "focal_length": "",
        "width": 0,
        "height": 0,
    }

    image, _ = open_metadata_image(path)
    if image is None:
        return meta

    try:
        meta["width"], meta["height"] = image.size
        exif = image.getexif() or {}
        exif_map = {EXIF_TAGS.get(key, key): value for key, value in exif.items()}

        capture_dt = parse_datetime_text(
            exif_map.get("DateTimeOriginal") or exif_map.get("DateTime") or ""
        )
        if capture_dt is not None:
            meta["capture_at"] = capture_dt.isoformat(timespec="seconds")
            meta["capture_source"] = "exif"

        meta["camera_model"] = str(exif_map.get("Model", "")).strip()
        meta["lens_model"] = str(exif_map.get("LensModel", "")).strip()

        iso_value = exif_map.get("ISOSpeedRatings") or exif_map.get("PhotographicSensitivity")
        if iso_value is not None:
            meta["iso"] = str(iso_value)

        aperture = exif_value_to_float(exif_map.get("FNumber"))
        if aperture is not None:
            meta["aperture"] = f"f/{aperture:.1f}".rstrip("0").rstrip(".")

        shutter = exposure_time_to_text(exif_map.get("ExposureTime"))
        if shutter:
            meta["shutter"] = shutter

        focal = exif_value_to_float(exif_map.get("FocalLength"))
        if focal is not None:
            meta["focal_length"] = f"{round(focal)}mm"
    finally:
        image.close()

    return meta


def compute_colorfulness(img: Image.Image) -> float:
    sample = img.convert("RGB").copy()
    sample.thumbnail((192, 192), Image.LANCZOS)
    pixels = list(sample.getdata())
    if not pixels:
        return 0.0

    rg_values = []
    yb_values = []
    for red, green, blue in pixels:
        rg_values.append(red - green)
        yb_values.append(0.5 * (red + green) - blue)

    def mean(values: list[float]) -> float:
        return sum(values) / len(values)

    def std(values: list[float]) -> float:
        average = mean(values)
        return math.sqrt(sum((value - average) ** 2 for value in values) / len(values))

    rg_std = std(rg_values)
    yb_std = std(yb_values)
    rg_mean = mean(rg_values)
    yb_mean = mean(yb_values)
    return round(math.sqrt(rg_std ** 2 + yb_std ** 2) + 0.3 * math.sqrt(rg_mean ** 2 + yb_mean ** 2), 2)


def compute_visual_features(path: Path) -> dict:
    image, source_name, visual_status = open_visual_preview_image(path)
    if image is None:
        return {
            "visual_status": visual_status,
            "visual_source": source_name,
            "brightness": None,
            "contrast": None,
            "sharpness": None,
            "colorfulness": None,
            "average_hash": "",
            "warmth_tag": "",
        }

    try:
        working = image.convert("RGB")
        working.thumbnail((VISUAL_ANALYSIS_MAX_EDGE, VISUAL_ANALYSIS_MAX_EDGE), Image.LANCZOS)
        gray = working.convert("L")
        gray_stat = ImageStat.Stat(gray)
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edge_stat = ImageStat.Stat(edges)
        rgb_stat = ImageStat.Stat(working)
        mean_red, _, mean_blue = rgb_stat.mean[0], rgb_stat.mean[1], rgb_stat.mean[2]

        warmth_tag = ""
        if mean_red - mean_blue > 12:
            warmth_tag = "暖色"
        elif mean_blue - mean_red > 12:
            warmth_tag = "冷色"

        return {
            "visual_status": visual_status,
            "visual_source": source_name,
            "brightness": round(gray_stat.mean[0], 2),
            "contrast": round(gray_stat.stddev[0], 2),
            "sharpness": round(edge_stat.var[0], 2),
            "colorfulness": compute_colorfulness(working),
            "average_hash": average_hash_bitstring(working),
            "warmth_tag": warmth_tag,
        }
    except OSError:
        return {
            "visual_status": "error",
            "visual_source": source_name,
            "brightness": None,
            "contrast": None,
            "sharpness": None,
            "colorfulness": None,
            "average_hash": "",
            "warmth_tag": "",
        }
    finally:
        image.close()


def build_asset_record(asset_id: str, path: Path, project_root: Path, intent: dict) -> dict:
    metadata = read_asset_metadata(path)
    features = compute_visual_features(path)
    capture_dt = parse_datetime_text(metadata.get("capture_at", ""))

    try:
        resolved_path = str(path.resolve(strict=False))
    except OSError:
        resolved_path = str(path)

    relative_path = asset_relative_path(path, project_root)

    orientation = ""
    if metadata.get("width") and metadata.get("height"):
        if metadata["width"] > metadata["height"]:
            orientation = "横图"
        elif metadata["width"] < metadata["height"]:
            orientation = "竖图"
        else:
            orientation = "方图"

    asset = {
        "id": asset_id,
        "project_name": "",
        "absolute_path": resolved_path,
        "relative_path": relative_path,
        "folder_name": path.parent.name,
        "extension": metadata["extension"],
        "file_name": metadata["file_name"],
        "file_size_bytes": metadata["file_size_bytes"],
        "modified_at": metadata["modified_at"],
        "capture_at": metadata["capture_at"],
        "capture_ts": capture_dt.timestamp() if capture_dt is not None else datetime.fromisoformat(metadata["modified_at"]).timestamp(),
        "capture_source": metadata["capture_source"],
        "camera_model": metadata["camera_model"],
        "lens_model": metadata["lens_model"],
        "iso": metadata["iso"],
        "aperture": metadata["aperture"],
        "shutter": metadata["shutter"],
        "focal_length": metadata["focal_length"],
        "width": metadata["width"],
        "height": metadata["height"],
        "orientation": orientation,
        "time_of_day": classify_time_of_day(capture_dt, features.get("brightness")),
        "visual_status": features["visual_status"],
        "visual_source": features["visual_source"],
        "brightness": features["brightness"],
        "contrast": features["contrast"],
        "sharpness": features["sharpness"],
        "colorfulness": features["colorfulness"],
        "average_hash": features["average_hash"],
        "warmth_tag": features["warmth_tag"],
        "content_hash": "",
        "tags": [],
        "scene_id": "",
        "burst_id": "",
        "duplicate_group": "",
        "duplicate_of": "",
        "reject_reasons": [],
        "quality_score": 0.0,
        "delivery_grade": "",
        "is_highlight_candidate": False,
        "is_reject_candidate": False,
    }
    asset["tags"] = infer_semantic_tags(asset, intent)
    return asset


def assign_scene_and_burst_ids(assets: list[dict]) -> None:
    ordered = sorted(assets, key=lambda item: (item["capture_ts"], item["relative_path"]))
    scene_idx = 0
    burst_idx = 0
    previous = None

    for asset in ordered:
        scene_break = previous is None
        if previous is not None:
            gap_minutes = (asset["capture_ts"] - previous["capture_ts"]) / 60
            same_folder = asset["folder_name"] == previous["folder_name"]
            same_camera = asset["camera_model"] == previous["camera_model"]
            scene_break = gap_minutes > SCENE_TIME_GAP_MINUTES or (not same_folder and gap_minutes > 8) or (not same_camera and gap_minutes > 5)

        if scene_break:
            scene_idx += 1
        asset["scene_id"] = f"scene_{scene_idx:03d}"

        burst_break = scene_break
        if previous is not None and not scene_break:
            gap_seconds = asset["capture_ts"] - previous["capture_ts"]
            burst_break = gap_seconds > BURST_TIME_GAP_SECONDS or asset["camera_model"] != previous["camera_model"]
        if burst_break:
            burst_idx += 1
        asset["burst_id"] = f"burst_{burst_idx:04d}"

        previous = asset


def provisional_quality_score(asset: dict) -> float:
    width = asset.get("width") or 0
    height = asset.get("height") or 0
    megapixels = (width * height) / 1_000_000 if width and height else 0
    brightness = asset.get("brightness")
    sharpness = asset.get("sharpness")
    contrast = asset.get("contrast")
    colorfulness = asset.get("colorfulness")

    score = 0.0
    score += min(megapixels / 24.0, 1.0) * 18
    score += min((sharpness or 0) / 120.0, 1.0) * 32
    score += min((contrast or 0) / 60.0, 1.0) * 10
    score += min((colorfulness or 0) / 50.0, 1.0) * 8

    if brightness is not None:
        exposure_penalty = min(abs(brightness - 128) / 128.0, 1.0)
        score += (1 - exposure_penalty) * 22

    if asset["extension"] in RAW_EXTS:
        score += 4
    return round(score, 2)


def mark_duplicate_groups(assets: list[dict]) -> list[dict]:
    duplicate_groups: list[dict] = []
    exact_map: dict[str, list[dict]] = defaultdict(list)

    for asset in assets:
        asset["duplicate_group"] = ""
        asset["duplicate_of"] = ""
        if not asset.get("content_hash"):
            try:
                asset["content_hash"] = file_sha1(Path(asset["absolute_path"]))
            except OSError:
                asset["content_hash"] = ""
        if asset["content_hash"]:
            exact_map[asset["content_hash"]].append(asset)

    group_counter = 0
    for _, items in exact_map.items():
        if len(items) <= 1:
            continue
        items.sort(key=provisional_quality_score, reverse=True)
        group_counter += 1
        group_id = f"dup_exact_{group_counter:03d}"
        keeper = items[0]
        keeper["duplicate_group"] = group_id
        for duplicate in items[1:]:
            duplicate["duplicate_group"] = group_id
            duplicate["duplicate_of"] = keeper["id"]
            duplicate["reject_reasons"].append("完全重复")
        duplicate_groups.append(
            {
                "id": group_id,
                "type": "exact",
                "keeper_id": keeper["id"],
                "member_ids": [item["id"] for item in items],
            }
        )

    burst_groups: dict[str, list[dict]] = defaultdict(list)
    for asset in assets:
        burst_groups[asset["burst_id"]].append(asset)

    for burst_assets in burst_groups.values():
        if len(burst_assets) <= 1:
            continue
        burst_assets.sort(key=provisional_quality_score, reverse=True)
        used: set[str] = set()
        for idx, keeper in enumerate(burst_assets):
            if keeper["id"] in used or not keeper.get("average_hash"):
                continue

            similar = [keeper]
            for candidate in burst_assets[idx + 1:]:
                if candidate["id"] in used or candidate.get("duplicate_of"):
                    continue
                if not candidate.get("average_hash"):
                    continue
                if hash_distance(keeper["average_hash"], candidate["average_hash"]) <= NEAR_DUPLICATE_HASH_DISTANCE:
                    similar.append(candidate)

            if len(similar) <= 1:
                continue

            group_counter += 1
            group_id = f"dup_near_{group_counter:03d}"
            keeper["duplicate_group"] = keeper["duplicate_group"] or group_id
            used.add(keeper["id"])
            for duplicate in similar[1:]:
                duplicate["duplicate_group"] = group_id
                duplicate["duplicate_of"] = keeper["id"]
                duplicate["reject_reasons"].append("近似重复")
                used.add(duplicate["id"])
            duplicate_groups.append(
                {
                    "id": group_id,
                    "type": "near",
                    "keeper_id": keeper["id"],
                    "member_ids": [item["id"] for item in similar],
                }
            )

    return duplicate_groups


def evaluate_reject_reasons(asset: dict) -> list[str]:
    reasons: list[str] = []
    width = int(asset.get("width") or 0)
    height = int(asset.get("height") or 0)
    sharpness = asset.get("sharpness")
    brightness = asset.get("brightness")

    if asset.get("duplicate_of"):
        reasons.append("duplicate")
    if asset.get("visual_status") == "unavailable":
        reasons.append("visual_unavailable")
    if isinstance(sharpness, (int, float)) and sharpness < 8:
        reasons.append("blur_risk")
    if isinstance(brightness, (int, float)) and brightness < 18:
        reasons.append("underexposed")
    if isinstance(brightness, (int, float)) and brightness > 242:
        reasons.append("overexposed")
    if width and height and width * height < 1_000_000:
        reasons.append("low_resolution")
    if asset.get("file_size_bytes", 0) < 80 * 1024:
        reasons.append("tiny_file")

    return normalize_string_list(reasons, limit=5)


def score_asset(asset: dict, culling_preference: str) -> float:
    score = provisional_quality_score(asset)
    reasons = evaluate_reject_reasons(asset)
    penalty = 0

    if "duplicate" in reasons:
        penalty += 45
    if "blur_risk" in reasons:
        penalty += 18
    if "underexposed" in reasons or "overexposed" in reasons:
        penalty += 12
    if "low_resolution" in reasons:
        penalty += 10
    if "tiny_file" in reasons:
        penalty += 12
    if "visual_unavailable" in reasons:
        penalty += 8

    score -= penalty
    if culling_preference == "conservative":
        score += 6
    elif culling_preference == "aggressive":
        score -= 6
    return round(score, 2)
def apply_curation_labels(assets: list[dict], culling_preference: str) -> tuple[list[str], list[str]]:
    highlight_ids: list[str] = []
    reject_ids: list[str] = []

    thresholds = {
        "conservative": {"reject": 22, "highlight": 58},
        "balanced": {"reject": 30, "highlight": 66},
        "aggressive": {"reject": 38, "highlight": 72},
    }
    current = thresholds.get(culling_preference or "balanced", thresholds["balanced"])

    for asset in assets:
        asset["reject_reasons"] = evaluate_reject_reasons(asset)
        asset["quality_score"] = score_asset(asset, culling_preference)
        asset["is_highlight_candidate"] = False
        asset["is_reject_candidate"] = False
        asset["delivery_grade"] = "C"

        if asset["duplicate_of"]:
            asset["is_reject_candidate"] = True
            asset["delivery_grade"] = "Reject"
            reject_ids.append(asset["id"])
            continue

        if asset["quality_score"] <= current["reject"] or len(asset["reject_reasons"]) >= 3:
            asset["is_reject_candidate"] = True
            asset["delivery_grade"] = "Reject"
            reject_ids.append(asset["id"])

    burst_best: dict[str, dict] = {}
    for asset in sorted(assets, key=lambda item: item["quality_score"], reverse=True):
        if asset["is_reject_candidate"]:
            continue
        burst_best.setdefault(asset["burst_id"], asset)

    for asset in assets:
        if asset["is_reject_candidate"]:
            continue
        if burst_best.get(asset["burst_id"], {}).get("id") == asset["id"] and asset["quality_score"] >= current["highlight"]:
            asset["is_highlight_candidate"] = True
            asset["delivery_grade"] = "A" if asset["quality_score"] >= 80 else "B"
            highlight_ids.append(asset["id"])
        elif asset["quality_score"] >= current["highlight"] + 8:
            asset["is_highlight_candidate"] = True
            asset["delivery_grade"] = "A" if asset["quality_score"] >= 82 else "B"
            highlight_ids.append(asset["id"])
        else:
            asset["delivery_grade"] = "B" if asset["quality_score"] >= 58 else "C"

    return highlight_ids, reject_ids


def build_scene_summaries(assets: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for asset in assets:
        grouped[asset["scene_id"]].append(asset)

    scenes: list[dict] = []
    for scene_id, items in grouped.items():
        ordered = sorted(items, key=lambda item: item["capture_ts"])
        start_dt = datetime.fromtimestamp(ordered[0]["capture_ts"])
        end_dt = datetime.fromtimestamp(ordered[-1]["capture_ts"])
        tag_counter = Counter(tag for item in items for tag in item.get("tags", []))
        scenes.append(
            {
                "scene_id": scene_id,
                "count": len(items),
                "burst_count": len({item["burst_id"] for item in items}),
                "time_range": f"{start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')}",
                "main_folder": ordered[0]["folder_name"],
                "top_tags": [tag for tag, _ in tag_counter.most_common(4)],
                "grade_counts": {
                    "A": sum(1 for item in items if item.get("delivery_grade") == "A"),
                    "B": sum(1 for item in items if item.get("delivery_grade") == "B"),
                    "C": sum(1 for item in items if item.get("delivery_grade") == "C"),
                    "Reject": sum(1 for item in items if item.get("delivery_grade") == "Reject"),
                },
            }
        )

    return sorted(scenes, key=lambda item: item["scene_id"])


def build_project_stats(index: dict) -> dict:
    assets = index["assets"]
    if not assets:
        return {}

    ext_counter = Counter(asset["extension"] for asset in assets)
    camera_counter = Counter(asset["camera_model"] or "未知设备" for asset in assets)
    lens_counter = Counter(asset["lens_model"] or "未知镜头" for asset in assets)
    time_counter = Counter(asset["time_of_day"] or "未知时段" for asset in assets)
    tag_counter = Counter(tag for asset in assets for tag in asset.get("tags", []))
    grade_counter = Counter(asset.get("delivery_grade", "C") or "C" for asset in assets)
    ordered = sorted(assets, key=lambda item: item["capture_ts"])
    start_date = datetime.fromtimestamp(ordered[0]["capture_ts"]).strftime("%Y-%m-%d")
    end_date = datetime.fromtimestamp(ordered[-1]["capture_ts"]).strftime("%Y-%m-%d")

    return {
        "total_assets": len(assets),
        "extensions": dict(ext_counter),
        "camera_top": [item for item, _ in camera_counter.most_common(3)],
        "lens_top": [item for item, _ in lens_counter.most_common(3)],
        "time_of_day_top": [item for item, _ in time_counter.most_common(4)],
        "top_tags": [item for item, _ in tag_counter.most_common(8)],
        "grade_counts": {
            "A": grade_counter.get("A", 0),
            "B": grade_counter.get("B", 0),
            "C": grade_counter.get("C", 0),
            "Reject": grade_counter.get("Reject", 0),
        },
        "highlight_count": len(index.get("highlight_ids", [])),
        "reject_count": len(index.get("reject_ids", [])),
        "duplicate_count": sum(1 for asset in assets if asset.get("duplicate_of")),
        "downsampled_visual_count": sum(
            1 for asset in assets if asset.get("visual_status") == "downsampled"
        ),
        "oversized_skipped_count": sum(
            1 for asset in assets if asset.get("visual_status") == "oversized_skipped"
        ),
        "cache_hit_count": int(index.get("cache_hit_count", 0) or 0),
        "rebuilt_asset_count": int(index.get("rebuilt_asset_count", len(assets)) or 0),
        "parallel_workers": int(index.get("parallel_workers", 1) or 1),
        "scene_count": len(index.get("scene_groups", [])),
        "date_range": f"{start_date} ~ {end_date}",
    }


def suggest_project_names(index: dict) -> list[str]:
    stats = index.get("stats", {})
    top_tags = [tag for tag in stats.get("top_tags", []) if tag not in {"横图", "竖图", "方图"}][:3]
    base_date = stats.get("date_range", "").split(" ~ ")[0]
    project_root_name = Path(index.get("project_root", ".")).name
    client = index.get("client_name", "")
    subject = index.get("subject_type", "")

    suggestions = [
        "_".join(part for part in [base_date, client, subject] if part),
        "_".join(part for part in [base_date, project_root_name, subject] if part),
        "_".join(part for part in [base_date, *top_tags[:2]] if part),
    ]

    deduped: list[str] = []
    seen: set[str] = set()
    for item in suggestions:
        cleaned = re.sub(r"_+", "_", item).strip("_")
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            deduped.append(cleaned)
    return deduped[:3]


def suggest_archive_rules(index: dict, profile: dict) -> dict:
    stats = index.get("stats", {})
    naming_rule = profile.get("naming_rule", "")
    folder_rule = profile.get("folder_rule", "")
    top_tags = stats.get("top_tags", [])[:3]
    base_date = stats.get("date_range", "").split(" ~ ")[0]
    client = index.get("client_name", "")
    subject = index.get("subject_type", "")

    return {
        "project_name_suggestions": suggest_project_names(index),
        "folder_suggestion": folder_rule or "/".join(
            part for part in [base_date[:4], f"{base_date}_{client or '项目'}_{subject or '摄影'}"] if part
        ),
        "naming_suggestion": naming_rule or "{date}_{scene}_{sequence}_{grade}",
        "recommended_tags": top_tags,
    }


def finalize_index(index: dict, profile: dict) -> dict:
    index["scene_groups"] = build_scene_summaries(index["assets"])
    index["stats"] = build_project_stats(index)
    index["suggestions"] = suggest_archive_rules(index, profile)
    return index


def save_project_index(index: dict) -> Path:
    cache_path = project_cache_path(Path(index["project_root"]))
    atomic_write_json(cache_path, build_asset_index_document(index))
    cleanup_json_cache(resolve_asset_index_dir(LEGACY_ASSET_INDEX_DIR), keep=ASSET_INDEX_CACHE_LIMIT)
    return cache_path


def load_project_index(cache_path: str | Path) -> dict | None:
    return migrate_asset_index_payload(read_json(cache_path))


def load_all_cached_indexes(limit: int = 10) -> list[dict]:
    asset_index_dir = resolve_asset_index_dir(LEGACY_ASSET_INDEX_DIR)
    if not asset_index_dir.exists():
        return []

    indexes: list[dict] = []
    cache_files = sorted(asset_index_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    for cache_file in cache_files[:limit]:
        loaded = load_project_index(cache_file)
        if loaded:
            indexes.append(loaded)
    return indexes


def rebuild_curation(index: dict, profile: dict, culling_preference: str) -> dict:
    preference = normalize_culling_preference(culling_preference) or index.get("culling_preference", "balanced")
    index["culling_preference"] = preference
    highlight_ids, reject_ids = apply_curation_labels(index["assets"], preference)
    index["highlight_ids"] = highlight_ids
    index["reject_ids"] = reject_ids
    return finalize_index(index, profile)


def index_project_assets(
    paths: list[Path],
    intent: dict,
    profile: dict,
    sink: EventSink | None = None,
) -> dict:
    event_sink = ensure_event_sink(sink)
    project_root = detect_project_root(paths)
    asset_paths = collect_asset_paths(paths)
    if not asset_paths:
        raise ValueError("No indexable image or RAW files were found under the given path.")

    project_name = infer_project_name(project_root, intent)
    culling_preference = normalize_culling_preference(intent.get("culling_preference", "")) or profile.get("culling_preference", "balanced")
    total = len(asset_paths)
    cache_path = project_cache_path(project_root)
    previous_index = load_project_index(cache_path)
    incremental_cache = build_incremental_asset_cache(previous_index)

    assets_by_key: dict[str, dict] = {}
    rebuild_plan: list[tuple[str, Path]] = []
    ordered_keys: list[str] = []

    event_sink.progress(f"  Building project index, found {total} file(s)...")
    for asset_path in asset_paths:
        signature = build_asset_cache_signature(asset_path, project_root)
        cache_key = str(signature["cache_key"])
        ordered_keys.append(cache_key)

        cached_asset = incremental_cache.get(cache_key)
        if can_reuse_cached_asset(cached_asset, signature):
            assets_by_key[cache_key] = reuse_cached_asset_record(
                cached_asset,
                asset_path,
                project_root,
                intent,
                project_name,
            )
            continue

        rebuild_plan.append((cache_key, asset_path))

    cache_hit_count = total - len(rebuild_plan)
    parallel_workers = choose_index_worker_count(len(rebuild_plan))
    if cache_hit_count:
        event_sink.progress(
            f"  Cache reuse: {cache_hit_count}/{total}; rebuild needed: {len(rebuild_plan)}"
        )
    if rebuild_plan:
        event_sink.progress(
            f"  Rebuilding visual and metadata features with {parallel_workers} worker(s)..."
        )

        def build_rebuilt_asset(task: tuple[str, Path]) -> tuple[str, dict]:
            cache_key, asset_path = task
            asset = build_asset_record("", asset_path, project_root, intent)
            asset["project_name"] = project_name
            return cache_key, asset

        if parallel_workers == 1:
            rebuilt_iter = map(build_rebuilt_asset, rebuild_plan)
        else:
            executor = ThreadPoolExecutor(max_workers=parallel_workers)
            try:
                rebuilt_iter = executor.map(build_rebuilt_asset, rebuild_plan)
                for idx, (cache_key, asset) in enumerate(rebuilt_iter, 1):
                    if idx == 1 or idx % 50 == 0 or idx == len(rebuild_plan):
                        event_sink.progress(f"  Rebuild progress: {idx}/{len(rebuild_plan)}")
                    assets_by_key[cache_key] = asset
            finally:
                executor.shutdown(wait=True)
            rebuilt_iter = None

        if parallel_workers == 1:
            for idx, (cache_key, asset) in enumerate(rebuilt_iter, 1):
                if idx == 1 or idx % 50 == 0 or idx == len(rebuild_plan):
                    event_sink.progress(f"  Rebuild progress: {idx}/{len(rebuild_plan)}")
                assets_by_key[cache_key] = asset
    else:
        event_sink.progress(f"  Progress: {total}/{total}")

    assets: list[dict] = []
    for idx, cache_key in enumerate(ordered_keys, 1):
        asset = assets_by_key[cache_key]
        asset["id"] = f"asset_{idx:05d}"
        asset["project_name"] = project_name
        assets.append(asset)

    assign_scene_and_burst_ids(assets)
    duplicate_groups = mark_duplicate_groups(assets)
    highlight_ids, reject_ids = apply_curation_labels(assets, culling_preference)

    index = {
        "indexed_at": datetime.now().isoformat(timespec="seconds"),
        "project_root": str(project_root),
        "project_name": project_name,
        "client_name": intent.get("client_name", ""),
        "subject_type": intent.get("subject_type", ""),
        "due_date": intent.get("due_date", ""),
        "culling_preference": culling_preference,
        "naming_rule": intent.get("naming_rule", "") or profile.get("naming_rule", ""),
        "folder_rule": intent.get("folder_rule", "") or profile.get("folder_rule", ""),
        "tag_taxonomy": intent.get("tag_taxonomy", "") or profile.get("tag_taxonomy", ""),
        "cache_hit_count": cache_hit_count,
        "rebuilt_asset_count": len(rebuild_plan),
        "parallel_workers": parallel_workers,
        "assets": assets,
        "duplicate_groups": duplicate_groups,
        "highlight_ids": highlight_ids,
        "reject_ids": reject_ids,
        "scene_groups": [],
        "stats": {},
        "suggestions": {},
    }
    return finalize_index(index, profile)


def build_search_summary(indexes: list[dict]) -> str:
    lines: list[str] = []
    for index in indexes[:8]:
        stats = index.get("stats", {})
        lines.append(
            f"- Project {index.get('project_name', '')}"
            f" | dates: {stats.get('date_range', '')}"
            f" | tags: {', '.join(stats.get('top_tags', [])[:6])}"
            f" | highlights: {stats.get('highlight_count', 0)}"
            f" | rejects: {stats.get('reject_count', 0)}"
        )
    return "\n".join(lines) if lines else "- No searchable indexes yet"
def last_day_of_month(any_day: date) -> date:
    next_month = (any_day.replace(day=28) + timedelta(days=4)).replace(day=1)
    return next_month - timedelta(days=1)


def fallback_search_filters(query: str) -> dict:
    today = datetime.now().date()
    filters = {
        "text_terms": [],
        "tags_any": [],
        "camera": "",
        "lens": "",
        "date_from": "",
        "date_to": "",
        "time_of_day": "",
        "delivery_grade": "",
        "only_highlights": False,
        "only_rejects": False,
        "only_duplicates": False,
        "limit": SEARCH_RESULT_LIMIT,
    }

    lowered = query.lower()
    if "上个月" in query:
        first_this_month = today.replace(day=1)
        last_prev_month = first_this_month - timedelta(days=1)
        first_prev_month = last_prev_month.replace(day=1)
        filters["date_from"] = first_prev_month.isoformat()
        filters["date_to"] = last_prev_month.isoformat()
    elif "本月" in query or "这个月" in query:
        filters["date_from"] = today.replace(day=1).isoformat()
        filters["date_to"] = today.isoformat()
    elif "去年" in query:
        year = today.year - 1
        filters["date_from"] = f"{year}-01-01"
        filters["date_to"] = f"{year}-12-31"

    if any(keyword in query for keyword in ("傍晚", "黄昏", "日落", "蓝调")):
        filters["time_of_day"] = "傍晚"
    elif any(keyword in query for keyword in ("夜", "夜景", "演出")):
        filters["time_of_day"] = "夜间"
    elif any(keyword in query for keyword in ("清晨", "日出", "早上")):
        filters["time_of_day"] = "清晨"

    if any(keyword in query for keyword in ("精选", "最好", "可交付", "候选")):
        filters["only_highlights"] = True
    if any(keyword in query for keyword in ("废片", "误触", "不可用")):
        filters["only_rejects"] = True
    if any(keyword in query for keyword in ("重复", "相似")):
        filters["only_duplicates"] = True

    semantic_tags = []
    for tag in ("beach", "portrait", "street", "landscape", "night", "indoor", "travel"):
        if tag in lowered:
            semantic_tags.append(tag)
    filters["tags_any"] = semantic_tags
    filters["text_terms"] = [query.strip()] if query.strip() else []
    return filters
def build_search_filter_prompt(indexes: list[dict]) -> str:
    return f"""You are the search-filter parser for the asset-management agent. Output JSON only.
Current date: {datetime.now().date().isoformat()}
Searchable project summary:
{build_search_summary(indexes)}

Return JSON in this shape:
{{
  "text_terms": ["free-text term"],
  "tags_any": ["beach", "portrait"],
  "camera": "",
  "lens": "",
  "date_from": "YYYY-MM-DD",
  "date_to": "YYYY-MM-DD",
  "time_of_day": "清晨 | 白天 | 傍晚 | 夜间 | ''",
  "delivery_grade": "A | B | C | Reject | ''",
  "only_highlights": false,
  "only_rejects": false,
  "only_duplicates": false,
  "limit": 20
}}
"""
def parse_search_filters(
    client: anthropic.Anthropic,
    indexes: list[dict],
    query: str,
) -> dict:
    fallback = fallback_search_filters(query)
    try:
        raw_chunks: list[str] = []
        with client.messages.stream(
            model=MODEL,
            max_tokens=500,
            system=build_search_filter_prompt(indexes),
            messages=[{"role": "user", "content": query.strip()}],
        ) as stream:
            for chunk in stream.text_stream:
                raw_chunks.append(chunk)
        raw_text = "".join(raw_chunks).strip()
        payload = extract_json_object(raw_text)
    except Exception as e:
        print(f"\n[素材搜索] 过滤条件解析失败（{type(e).__name__}: {e}），使用规则兜底。\n")
        return fallback

    return {
        "text_terms": normalize_string_list(payload.get("text_terms", []), limit=5) or fallback["text_terms"],
        "tags_any": normalize_string_list(payload.get("tags_any", []), limit=6) or fallback["tags_any"],
        "camera": str(payload.get("camera", "")).strip(),
        "lens": str(payload.get("lens", "")).strip(),
        "date_from": str(payload.get("date_from", "")).strip(),
        "date_to": str(payload.get("date_to", "")).strip(),
        "time_of_day": str(payload.get("time_of_day", "")).strip() or fallback["time_of_day"],
        "delivery_grade": str(payload.get("delivery_grade", "")).strip(),
        "only_highlights": bool(payload.get("only_highlights", fallback["only_highlights"])),
        "only_rejects": bool(payload.get("only_rejects", fallback["only_rejects"])),
        "only_duplicates": bool(payload.get("only_duplicates", fallback["only_duplicates"])),
        "limit": min(max(int(payload.get("limit", fallback["limit"]) or SEARCH_RESULT_LIMIT), 1), SEARCH_RESULT_LIMIT),
    }


def date_in_range(date_text: str, start_text: str, end_text: str) -> bool:
    if not date_text:
        return False
    try:
        current = datetime.fromisoformat(date_text).date()
    except ValueError:
        return False

    if start_text:
        try:
            start = date.fromisoformat(start_text)
            if current < start:
                return False
        except ValueError:
            pass
    if end_text:
        try:
            end = date.fromisoformat(end_text)
            if current > end:
                return False
        except ValueError:
            pass
    return True


def asset_matches_filters(asset: dict, filters: dict) -> tuple[bool, int]:
    score = 0
    text_blob = " ".join(
        str(part).lower()
        for part in [
            asset.get("project_name", ""),
            asset.get("relative_path", ""),
            asset.get("folder_name", ""),
            " ".join(asset.get("tags", [])),
            asset.get("camera_model", ""),
            asset.get("lens_model", ""),
        ]
    )

    if filters.get("camera") and filters["camera"].lower() not in asset.get("camera_model", "").lower():
        return False, 0
    if filters.get("lens") and filters["lens"].lower() not in asset.get("lens_model", "").lower():
        return False, 0
    if filters.get("time_of_day") and filters["time_of_day"] != asset.get("time_of_day"):
        return False, 0
    if filters.get("delivery_grade") and filters["delivery_grade"] != asset.get("delivery_grade"):
        return False, 0
    if filters.get("only_highlights") and not asset.get("is_highlight_candidate"):
        return False, 0
    if filters.get("only_rejects") and not asset.get("is_reject_candidate"):
        return False, 0
    if filters.get("only_duplicates") and not asset.get("duplicate_of"):
        return False, 0
    if filters.get("date_from") or filters.get("date_to"):
        if not date_in_range(asset.get("capture_at", ""), filters.get("date_from", ""), filters.get("date_to", "")):
            return False, 0

    tags_any = filters.get("tags_any") or []
    if tags_any:
        matched_tags = [tag for tag in tags_any if tag in asset.get("tags", []) or tag.lower() in text_blob]
        if not matched_tags:
            return False, 0
        score += len(matched_tags) * 12

    text_terms = filters.get("text_terms") or []
    for term in text_terms:
        if term.lower() in text_blob:
            score += 8
        else:
            return False, 0

    score += int(asset.get("quality_score", 0))
    if asset.get("is_highlight_candidate"):
        score += 15
    if asset.get("duplicate_of"):
        score -= 20
    if asset.get("is_reject_candidate"):
        score -= 10
    return True, score


def search_index_records(indexes: list[dict], filters: dict) -> list[dict]:
    matches: list[dict] = []
    for index in indexes:
        for asset in index.get("assets", []):
            matched, score = asset_matches_filters(asset, filters)
            if not matched:
                continue
            enriched = {**asset, "project_name": index.get("project_name", asset.get("project_name", "")), "_match_score": score}
            matches.append(enriched)

    matches.sort(key=lambda item: item["_match_score"], reverse=True)
    return matches[: filters.get("limit", SEARCH_RESULT_LIMIT)]


def select_assets_by_ids(index: dict, ids: list[str]) -> list[dict]:
    wanted = set(ids)
    return [asset for asset in index.get("assets", []) if asset["id"] in wanted]


def select_assets_by_grade(index: dict, grade: str) -> list[dict]:
    return [
        asset for asset in index.get("assets", [])
        if asset.get("delivery_grade") == grade
    ]


def select_curated_assets(index: dict) -> list[dict]:
    return [
        asset for asset in index.get("assets", [])
        if asset.get("delivery_grade") in {"A", "B"}
    ]


def prepare_handoff_assets(index: dict, destination: str) -> tuple[list[dict], str]:
    if destination == "coach":
        candidates = sort_assets_for_display(
            select_assets_by_ids(index, index.get("reject_ids", []))
        )[:MAX_HANDOFF_ITEMS]
        note = "这些清理样片更适合继续流转到学习教练做问题复盘。"
    else:
        candidates = sort_assets_for_display(select_curated_assets(index))[:MAX_HANDOFF_ITEMS]
        note = "这些典藏 / 佳片更适合继续流转到后期辅助做统一调色和参数建议。"
    return candidates, note


def render_index_response(index: dict, cache_path: Path) -> str:
    stats = index.get("stats", {})
    scene_groups = index.get("scene_groups", [])
    suggestions = index.get("suggestions", {})
    grade_counts = stats.get("grade_counts", {})

    lines = [
        f"项目已完成索引：{index.get('project_name', '未命名项目')}",
        "",
        "项目概览：",
        f"- 路径：{index.get('project_root', '')}",
        f"- 日期范围：{stats.get('date_range', '')}",
        f"- 素材总数：{stats.get('total_assets', 0)}",
        f"- 场景分组：{stats.get('scene_count', 0)}",
        f"- 典藏：{grade_counts.get('A', 0)}",
        f"- 佳片：{grade_counts.get('B', 0)}",
        f"- 留存：{grade_counts.get('C', 0)}",
        f"- 清理：{grade_counts.get('Reject', 0)}",
        f"- 重复片：{stats.get('duplicate_count', 0)}",
        f"- 筛片偏好：{format_culling_preference(index.get('culling_preference', 'balanced'))}",
    ]

    if stats.get("downsampled_visual_count", 0):
        lines.append(f"- 超大图降采样分析：{stats.get('downsampled_visual_count', 0)}")
    if stats.get("oversized_skipped_count", 0):
        lines.append(f"- 超大图跳过视觉特征：{stats.get('oversized_skipped_count', 0)}")
    if stats.get("cache_hit_count", 0):
        lines.append(f"- 缓存复用：{stats.get('cache_hit_count', 0)}")
    if stats.get("rebuilt_asset_count", 0):
        lines.append(f"- 本轮重建：{stats.get('rebuilt_asset_count', 0)}")
    if stats.get("parallel_workers", 1) > 1:
        lines.append(f"- 并行索引线程：{stats.get('parallel_workers', 1)}")
    if stats.get("top_tags"):
        lines.append(f"- 主要标签：{', '.join(stats['top_tags'][:6])}")
    if stats.get("camera_top"):
        lines.append(f"- 常用设备：{', '.join(stats['camera_top'][:3])}")
    if stats.get("downsampled_visual_count", 0) or stats.get("oversized_skipped_count", 0):
        lines.append("- 说明：超大文件已按降级策略处理，以保持建索引稳定。")

    if scene_groups:
        lines.extend(["", "场景分组预览："])
        for scene in scene_groups[:5]:
            scene_grade_counts = scene.get("grade_counts", {})
            lines.append(
                f"- {scene['scene_id']}：{scene['count']} 张，{scene['time_range']}，"
                f"标签 {' / '.join(scene['top_tags'][:3]) or '无'}"
            )
            lines.append(
                "  分档："
                f"典藏 {scene_grade_counts.get('A', 0)} / "
                f"佳片 {scene_grade_counts.get('B', 0)} / "
                f"留存 {scene_grade_counts.get('C', 0)} / "
                f"清理 {scene_grade_counts.get('Reject', 0)}"
            )

    lines.extend(["", "命名与归档建议："])
    for suggestion in suggestions.get("project_name_suggestions", [])[:3]:
        lines.append(f"- 项目命名建议：{suggestion}")
    if suggestions.get("folder_suggestion"):
        lines.append(f"- 文件夹建议：{suggestions['folder_suggestion']}")
    if suggestions.get("naming_suggestion"):
        lines.append(f"- 文件命名规则建议：{suggestions['naming_suggestion']}")
    if suggestions.get("recommended_tags"):
        lines.append(f"- 建议保留的稳定标签：{', '.join(suggestions['recommended_tags'][:5])}")

    lines.extend([
        "",
        f"[索引缓存] {cache_path}",
        "继续可以直接说：看典藏 / 看佳片 / 看留存 / 看清理 / 看重复片 / 把典藏或佳片送去后期辅助 / 把清理样片送去学习教练复盘",
    ])
    return "\n".join(lines).strip()


def render_asset_subset(title: str, assets: list[dict], empty_text: str) -> str:
    if not assets:
        return empty_text

    lines = [title]
    for idx, asset in enumerate(sort_assets_for_display(assets)[:20], 1):
        reason_text = ""
        if asset.get("reject_reasons"):
            reason_text = f"；原因：{', '.join(asset['reject_reasons'][:3])}"
        elif asset.get("duplicate_of"):
            reason_text = f"；重复自：{asset['duplicate_of']}"
        lines.append(
            f"{idx}. [{format_delivery_grade(asset.get('delivery_grade', ''))}] {asset.get('relative_path', '')}"
            f"；场景 {asset.get('scene_id', '')}"
            f"；得分 {asset.get('quality_score', 0)}"
            f"{reason_text}"
        )
    return "\n".join(lines).strip()


def render_search_response(query: str, filters: dict, results: list[dict]) -> str:
    if not results:
        return f"没有素材匹配“{query}”。可以放宽日期范围或标签条件。"

    lines = [
        f"搜索结果：{query}",
        "",
        f"- 匹配数量：{len(results)}",
    ]
    if filters.get("date_from") or filters.get("date_to"):
        lines.append(f"- 日期范围：{filters.get('date_from', '')} ~ {filters.get('date_to', '')}")
    if filters.get("time_of_day"):
        lines.append(f"- 时段：{filters['time_of_day']}")
    if filters.get("tags_any"):
        lines.append(f"- 标签：{', '.join(filters['tags_any'])}")

    lines.append("")
    for asset in results:
        lines.append(
            f"- {asset.get('project_name', '')} | [{format_delivery_grade(asset.get('delivery_grade', ''))}] {asset.get('relative_path', '')}"
            f"；{asset.get('capture_at', '')[:10]} {asset.get('time_of_day', '')}"
            f"；标签 {' / '.join(asset.get('tags', [])[:4]) or '无'}"
        )
    return "\n".join(lines).strip()


def render_handoff_response(destination: str, assets: list[dict], note: str) -> str:
    if not assets:
        if destination == "coach":
            return "当前还没有明确适合送去学习教练的清理样片，先看看清理列表。"
        return "当前还没有明确适合送去后期辅助的典藏或佳片，先看看典藏 / 佳片列表。"

    destination_label = "学习教练" if destination == "coach" else "后期辅助"
    lines = [
        f"已为 {destination_label} 准备素材入口：",
        "",
    ]
    for asset in assets:
        lines.append(f"- {asset.get('absolute_path', '')}")
    lines.extend(["", note])
    return "\n".join(lines).strip()


def resolve_asset_context_paths(session_state: dict) -> list[Path]:
    for key in ("current_focus_paths", "last_handoff_paths"):
        raw_paths = session_state.get(key, []) or []
        paths = [Path(path_text) for path_text in raw_paths if str(path_text).strip()]
        existing_paths = [path for path in paths if path.exists()]
        if existing_paths:
            return existing_paths
    return []


def resolve_retryable_handoff(session_state: dict) -> tuple[str, list[dict], str] | None:
    destination = str(session_state.get("last_handoff_destination", "")).strip()
    assets = session_state.get("last_handoff_assets", []) or []
    note = str(session_state.get("last_handoff_note", "")).strip()
    if not destination or not assets:
        return None
    return destination, copy.deepcopy(list(assets)), note


def update_asset_session_state(
    session_state: dict,
    index: dict | None = None,
    cache_path: Path | None = None,
    search_query: str = "",
    search_filters: dict | None = None,
    search_results: list[dict] | None = None,
    handoff_destination: str = "",
    handoff_paths: list[str] | None = None,
    handoff_assets: list[dict] | None = None,
    handoff_note: str | None = None,
    focus_paths: list[str] | None = None,
) -> dict:
    updated = {**DEFAULT_ASSET_SESSION_STATE, **session_state}

    if index is not None:
        updated["current_project_root"] = index.get("project_root", "")
        updated["current_project_name"] = index.get("project_name", "")
        updated["current_culling_preference"] = index.get("culling_preference", "balanced")
        updated["last_highlight_ids"] = list(index.get("highlight_ids", []))[:20]
        updated["last_reject_ids"] = list(index.get("reject_ids", []))[:20]
        updated["last_duplicate_groups"] = [group["id"] for group in index.get("duplicate_groups", [])[:12]]
        grade_counts = index.get("stats", {}).get("grade_counts", {})
        updated["last_summary"] = (
            f"{index.get('project_name', '')}: {index.get('stats', {}).get('total_assets', 0)} assets, "
            f"{grade_counts.get('A', 0)} gallery, "
            f"{grade_counts.get('B', 0)} featured, "
            f"{grade_counts.get('Reject', 0)} reject"
        )
    if cache_path is not None:
        updated["last_index_cache"] = str(cache_path)
    if search_query:
        updated["last_search_query"] = search_query
    if search_filters is not None:
        updated["last_search_filters"] = search_filters
    if search_results is not None:
        result_paths = [
            str(asset.get("absolute_path", "")).strip()
            for asset in search_results
            if str(asset.get("absolute_path", "")).strip()
        ]
        updated["last_search_result_paths"] = result_paths
        updated["current_focus_paths"] = result_paths[:1] if len(result_paths) == 1 else []
    if handoff_destination:
        updated["last_handoff_destination"] = handoff_destination
    if handoff_paths is not None:
        updated["last_handoff_paths"] = list(handoff_paths)
    if handoff_assets is not None:
        updated["last_handoff_assets"] = copy.deepcopy(list(handoff_assets))
    if handoff_note is not None:
        updated["last_handoff_note"] = str(handoff_note).strip()
    if focus_paths is not None:
        updated["current_focus_paths"] = [str(path).strip() for path in focus_paths if str(path).strip()]
    return updated
def print_banner() -> None:
    print("=" * 60)
    print("  摄影全栈 Agent - V4 素材管理")
    print("=" * 60)


def print_help() -> None:
    print(
        """
可用命令：
  [项目路径] :: 偏好说明                 导入并建立项目索引
  看典藏                                 查看 A 档首选
  看佳片                                 查看 B 档可交付
  看留存                                 查看 C 档一般保留
  看清理                                 查看 Reject 档待清理
  看重复片                               查看重复片和相似片
  命名 / 标签 / 归档建议                 查看建议
  把典藏或佳片送去后期辅助               准备后期流转
  把清理样片送去学习教练复盘             准备学习流转
  profile                                查看当前档案
  reset                                  重置素材上下文
  quit / exit                            退出
"""
    )
    print_input_format_tips()


def legacy_standalone_main() -> None:
    print_banner()
    print("请使用 photo.py 作为统一入口。这个独立 CLI 仅保留给调试使用。")
    main()


def main() -> None:
    from photo import main as unified_main

    unified_main(preferred_module="asset", source_cli="photo_v4.py")


if __name__ == "__main__":
    main()

