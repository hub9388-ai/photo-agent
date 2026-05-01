from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps
from starlette.concurrency import run_in_threadpool

from app.agents.base import LegacyAgentService
from app.orchestration.event_bus import AgentEventSink
from app.schemas.agent import AssetAgentRequest
from app.schemas.asset_score import AssetScoreResponse, ScoredAsset, ScoredAssetMetadata
from app.schemas.result import AgentResult
from app.storage.media_store import MediaStore


class AssetAgentService(LegacyAgentService):
    def __init__(self) -> None:
        super().__init__(
            agent_name="asset",
            module_name="photo_v4",
            required_callables=(
                "index_project_assets",
                "render_index_response",
                "save_project_index",
                "search_index_records",
                "prepare_handoff_assets",
                "build_asset_record",
                "assign_scene_and_burst_ids",
                "mark_duplicate_groups",
                "apply_curation_labels",
            ),
        )

    async def run(self, request: AssetAgentRequest, sink: AgentEventSink) -> AgentResult:
        return await run_in_threadpool(self._run_sync, request, sink)

    def _run_sync(self, request: AssetAgentRequest, sink: AgentEventSink) -> AgentResult:
        if request.task_mode != "import_project":
            raise ValueError(f"Unsupported asset task mode in stage 7: {request.task_mode}")
        if not request.project_root:
            raise ValueError("project_root is required for asset import.")

        legacy = self.load_legacy_module()
        sink.progress_step("scanning_files", "正在扫描项目素材", progress=0.1)

        profile = legacy.ensure_asset_profile_fields(legacy.load_profile())
        intent = _build_asset_import_intent(request)

        sink.progress_step("building_index", "正在建立素材索引", progress=0.25)
        index = legacy.index_project_assets(
            [Path(request.project_root)],
            intent,
            profile,
            sink=sink,
        )

        sink.progress_step("saving_index", "正在保存素材索引", progress=0.9)
        cache_path = legacy.save_project_index(index)
        visible_text = legacy.render_index_response(index, cache_path)
        payload = {
            "projectId": request.project_id,
            "projectRoot": request.project_root,
            "cachePath": str(cache_path),
            "index": index,
            "stats": index.get("stats", {}),
            "suggestions": index.get("suggestions", {}),
            "duplicateGroups": index.get("duplicate_groups", []),
            "highlightIds": index.get("highlight_ids", []),
            "rejectIds": index.get("reject_ids", []),
        }

        sink.progress_step("finalizing_result", "正在整理素材管理结果", progress=0.98)
        return AgentResult(
            id=f"result_{uuid.uuid4().hex}",
            job_id=request.job_id,
            agent="asset",
            status="succeeded",
            summary=str(index.get("stats", {}).get("total_assets", 0)) + " assets indexed",
            content=visible_text,
            payload=payload,
        )

    async def score_uploaded_media(
        self,
        media_ids: list[str],
        media_store: MediaStore,
        *,
        culling_preference: str = "balanced",
    ) -> AssetScoreResponse:
        return await run_in_threadpool(
            self._score_uploaded_media_sync,
            media_ids,
            media_store,
            culling_preference,
        )

    def _score_uploaded_media_sync(
        self,
        media_ids: list[str],
        media_store: MediaStore,
        culling_preference: str,
    ) -> AssetScoreResponse:
        legacy = self.load_legacy_module()
        media_assets = [media_store.get(media_id) for media_id in media_ids]
        records: list[dict] = []
        media_by_asset_id: dict[str, object] = {}
        project_root = media_store.originals_dir

        intent = {
            "task_mode": "import_project",
            "project_name": "uploaded_media",
            "culling_preference": culling_preference or "balanced",
        }

        for index, media_asset in enumerate(media_assets, 1):
            asset_id = f"asset_{media_asset.id}"
            path = Path(media_asset.storage_uri)
            record = legacy.build_asset_record(asset_id, path, project_root, intent)
            record["media_id"] = media_asset.id
            record["preview_url"] = media_asset.preview_url
            record["mime_type"] = media_asset.content_type
            record["file_name"] = media_asset.filename
            record["relative_path"] = media_asset.filename
            record["sort_order"] = index
            record["_upload_metadata"] = _fresh_media_metadata(media_asset, media_store)
            records.append(record)
            media_by_asset_id[asset_id] = media_asset

        legacy.assign_scene_and_burst_ids(records)
        duplicate_groups = legacy.mark_duplicate_groups(records)
        legacy.apply_curation_labels(records, culling_preference or "balanced")

        scored = [
            _scored_asset_from_legacy_record(record, media_by_asset_id.get(str(record.get("id", ""))))
            for record in sorted(records, key=lambda item: int(item.get("sort_order", 0) or 0))
        ]
        return AssetScoreResponse(
            assets=scored,
            duplicate_groups=duplicate_groups,
            scoring_method="asset_agent_visual_features",
            warnings=[],
        )


def _build_asset_import_intent(request: AssetAgentRequest) -> dict:
    context = request.context
    return {
        "task_mode": "import_project",
        "project_name": str(context.get("project_name") or context.get("projectName") or request.project_id or ""),
        "client_name": str(context.get("client_name") or context.get("clientName") or ""),
        "subject_type": str(context.get("subject_type") or context.get("subjectType") or ""),
        "due_date": str(context.get("due_date") or context.get("dueDate") or ""),
        "culling_preference": str(context.get("culling_preference") or context.get("cullingPreference") or ""),
        "naming_rule": str(context.get("naming_rule") or context.get("namingRule") or ""),
        "folder_rule": str(context.get("folder_rule") or context.get("folderRule") or ""),
        "tag_taxonomy": str(context.get("tag_taxonomy") or context.get("tagTaxonomy") or ""),
    }


def _grade_from_record(record: dict) -> str:
    if record.get("duplicate_of"):
        return "duplicate"
    grade = str(record.get("delivery_grade") or "").strip()
    if grade.lower() == "reject":
        return "reject"
    if grade in {"A", "B", "C"}:
        return grade
    return "unscored"


def _asset_reasons(record: dict) -> list[str]:
    reasons: list[str] = []
    score = record.get("quality_score")
    if isinstance(score, (int, float)):
        reasons.append(f"AssetAgent 视觉质量评分 {round(float(score), 1)}")
    if record.get("brightness") is not None:
        reasons.append(f"亮度 {record.get('brightness')}")
    if record.get("sharpness") is not None:
        reasons.append(f"清晰度 {record.get('sharpness')}")
    if record.get("contrast") is not None:
        reasons.append(f"对比度 {record.get('contrast')}")
    if record.get("duplicate_of"):
        reasons.append(f"与 {record.get('duplicate_of')} 判定为重复或近似重复")
    if record.get("visual_status") and record.get("visual_status") != "ok":
        reasons.append(f"视觉特征状态：{record.get('visual_status')}")
    return reasons[:6]


def _string_value(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _format_decimal(value: Any) -> str | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return str(int(number)) if number.is_integer() else f"{number:.1f}".rstrip("0").rstrip(".")


def _format_aperture(value: Any) -> str | None:
    raw = _string_value(value)
    if not raw:
        return None
    if raw.lower().startswith("f/"):
        return raw
    normalized = _format_decimal(value)
    return f"f/{normalized}" if normalized else raw


def _format_focal_length(value: Any) -> str | None:
    raw = _string_value(value)
    if not raw:
        return None
    if raw.lower().endswith("mm"):
        return raw
    normalized = _format_decimal(value)
    return f"{normalized}mm" if normalized else raw


def _format_shutter(value: Any) -> str | None:
    raw = _string_value(value)
    if not raw:
        return None
    if "/" in raw or raw.lower().endswith("s"):
        return raw
    try:
        number = float(value)
    except (TypeError, ValueError):
        return raw
    if number >= 1:
        normalized = _format_decimal(number)
        return f"{normalized}s" if normalized else raw
    if number > 0:
        return f"1/{round(1 / number)}s"
    return raw


def _media_metadata(media_asset: object | None) -> dict[str, Any]:
    metadata = getattr(media_asset, "metadata", None)
    if not isinstance(metadata, dict):
        return {}
    exif = metadata.get("exif")
    if not isinstance(exif, dict):
        exif = {}
    return {**metadata, **exif}


def _fresh_media_metadata(media_asset: object | None, media_store: MediaStore) -> dict[str, Any]:
    metadata = _media_metadata(media_asset)
    exif = metadata.get("exif")
    has_rich_exif = isinstance(exif, dict) and any(
        exif.get(key)
        for key in (
            "FocalLength",
            "ExposureTime",
            "FNumber",
            "ISOSpeedRatings",
            "PhotographicSensitivity",
            "DateTimeOriginal",
        )
    )
    if has_rich_exif:
        return metadata

    storage_uri = getattr(media_asset, "storage_uri", None)
    if not storage_uri:
        return metadata

    path = Path(str(storage_uri))
    if not path.exists():
        return metadata

    try:
        with Image.open(path) as image:
            image.load()
            image = ImageOps.exif_transpose(image)
            refreshed = media_store._extract_metadata(
                image=image,
                file_name=str(getattr(media_asset, "filename", path.name)),
                content_type=str(getattr(media_asset, "content_type", "image/jpeg")),
                size_bytes=int(getattr(media_asset, "size_bytes", path.stat().st_size) or path.stat().st_size),
            )
    except OSError:
        return metadata

    refreshed_exif = refreshed.get("exif") if isinstance(refreshed.get("exif"), dict) else {}
    return {
        **metadata,
        **refreshed,
        **refreshed_exif,
        "exif": {
            **(exif if isinstance(exif, dict) else {}),
            **refreshed_exif,
        },
    }


def _media_camera_name(metadata: dict[str, Any]) -> str | None:
    direct = _string_value(
        metadata.get("camera")
        or metadata.get("Camera")
        or metadata.get("camera_model")
        or metadata.get("cameraModel")
        or metadata.get("Model")
    )
    make = _string_value(metadata.get("Make") or metadata.get("make"))
    model = _string_value(metadata.get("Model") or metadata.get("model"))
    if make and model and (not direct or make not in direct):
        return f"{make} {model}"
    return direct or model or make


def _scored_asset_from_legacy_record(record: dict, media_asset: object | None) -> ScoredAsset:
    upload_metadata = record.get("_upload_metadata")
    media_metadata = upload_metadata if isinstance(upload_metadata, dict) else _media_metadata(media_asset)
    metadata = ScoredAssetMetadata(
        iso=_string_value(
            record.get("iso")
            or media_metadata.get("iso")
            or media_metadata.get("ISO")
            or media_metadata.get("ISOSpeedRatings")
            or media_metadata.get("PhotographicSensitivity")
        ),
        aperture=_format_aperture(
            record.get("aperture")
            or media_metadata.get("aperture")
            or media_metadata.get("FNumber")
            or media_metadata.get("fNumber")
        ),
        shutter=_format_shutter(
            record.get("shutter")
            or media_metadata.get("shutter")
            or media_metadata.get("ExposureTime")
            or media_metadata.get("exposureTime")
        ),
        focal_length=_format_focal_length(
            record.get("focal_length")
            or media_metadata.get("focalLength")
            or media_metadata.get("FocalLength")
        ),
        camera=_string_value(record.get("camera_model")) or _media_camera_name(media_metadata),
        captured_at=_string_value(
            record.get("capture_at")
            or media_metadata.get("capturedAt")
            or media_metadata.get("captured_at")
            or media_metadata.get("DateTimeOriginal")
        ),
        width=record.get("width") or media_metadata.get("width") or None,
        height=record.get("height") or media_metadata.get("height") or None,
        location=_string_value(media_metadata.get("location") or media_metadata.get("city") or media_metadata.get("address")),
        file_size=_string_value(record.get("file_size_bytes") or media_metadata.get("sizeBytes") or media_metadata.get("fileSize")),
        brightness=record.get("brightness"),
        sharpness=record.get("sharpness"),
        contrast=record.get("contrast"),
        colorfulness=record.get("colorfulness"),
        visual_status=str(record.get("visual_status") or "") or None,
    )
    score = record.get("quality_score")
    preview_url = getattr(media_asset, "preview_url", None) or record.get("preview_url")
    content_type = getattr(media_asset, "content_type", None) or record.get("mime_type")
    created_at = getattr(media_asset, "created_at", None)
    return ScoredAsset(
        asset_id=str(record.get("id", "")),
        media_id=str(record.get("media_id", "")),
        file_name=str(record.get("file_name") or record.get("relative_path") or ""),
        preview_url=preview_url,
        mime_type=content_type,
        media_category="image",
        metadata=metadata,
        grade=_grade_from_record(record),
        score=round(float(score), 2) if isinstance(score, (int, float)) else None,
        tags=[str(item) for item in record.get("tags", [])[:8]],
        ai_reasons=_asset_reasons(record),
        issues=[str(item) for item in record.get("reject_reasons", [])],
        duplicate_group_id=str(record.get("duplicate_group") or "") or None,
        duplicate_of=str(record.get("duplicate_of") or "") or None,
        upload_status="uploaded",
        error_message=None,
        created_at=created_at,
    )


_ASSET_AGENT_SERVICE: AssetAgentService | None = None


def get_asset_agent_service() -> AssetAgentService:
    global _ASSET_AGENT_SERVICE
    if _ASSET_AGENT_SERVICE is None:
        _ASSET_AGENT_SERVICE = AssetAgentService()
    return _ASSET_AGENT_SERVICE
