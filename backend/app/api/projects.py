from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends

from app.core.errors import ApiError
from app.core.settings import Settings, get_settings
from app.orchestration.event_bus import EventBus, get_event_bus
from app.orchestration.job_runner import JobRunner, get_job_runner
from app.schemas.event import AgentEvent
from app.schemas.job import CreateJobRequest
from app.schemas.project import (
    AssetImportRequest,
    AssetImportResponse,
    ProjectAssetsResponse,
    asset_import_response_from_job,
    project_asset_summary_from_record,
)
from app.schemas.response import ErrorResponse
from app.storage.event_store import EventStore, get_event_store
from app.storage.job_store import JobStore, get_job_store
from app.storage.result_store import ResultStore, get_result_store

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post(
    "/{project_id}/assets/import",
    response_model=AssetImportResponse,
    status_code=202,
    summary="Import a local project folder and start asset indexing",
    responses={400: {"model": ErrorResponse}},
)
async def import_project_assets(
    project_id: str,
    request: AssetImportRequest,
    settings: Settings = Depends(get_settings),
    job_store: JobStore = Depends(get_job_store),
    event_store: EventStore = Depends(get_event_store),
    event_bus: EventBus = Depends(get_event_bus),
    job_runner: JobRunner = Depends(get_job_runner),
) -> AssetImportResponse:
    project_root = _validate_project_root(request.project_root, settings)
    context = {
        **request.context,
        "project_id": project_id,
        "project_root": str(project_root),
        "project_name": request.project_name or project_id,
        "culling_preference": request.culling_preference,
        "asset_task_mode": "import_project",
    }
    job = job_store.create_from_request(
        CreateJobRequest(
            type="asset_indexing",
            trigger="user",
            media_ids=[],
            agents=["asset"],
            user_goal=request.user_goal or "Import and index project assets.",
            context=context,
        )
    )
    event = AgentEvent(
        id=f"evt_{job.id}_created",
        job_id=job.id,
        seq=event_store.next_seq(job.id),
        agent=None,
        type="job.created",
        message="素材索引任务已创建",
        payload={"agents": job.agents, "projectId": project_id, "projectRoot": str(project_root)},
    )
    event_store.append_if_persisted(event)
    await event_bus.publish(event)
    job_runner.start(job.id)
    return asset_import_response_from_job(project_id, job.id, job.status)


@router.get(
    "/{project_id}/assets",
    response_model=ProjectAssetsResponse,
    summary="List indexed project assets",
    responses={404: {"model": ErrorResponse}},
)
def list_project_assets(
    project_id: str,
    job_id: str | None = None,
    grade: str | None = None,
    job_store: JobStore = Depends(get_job_store),
    result_store: ResultStore = Depends(get_result_store),
) -> ProjectAssetsResponse:
    job, index = _resolve_asset_index(
        project_id=project_id,
        job_id=job_id,
        job_store=job_store,
        result_store=result_store,
    )
    assets = list(index.get("assets", []))
    if grade:
        normalized_grade = "Reject" if grade.lower() == "reject" else grade.upper()
        assets = [
            asset
            for asset in assets
            if str(asset.get("delivery_grade", "")).lower() == normalized_grade.lower()
        ]
    return ProjectAssetsResponse(
        project_id=project_id,
        job_id=job.id,
        status=job.status,
        assets=[project_asset_summary_from_record(asset) for asset in assets],
        stats=index.get("stats", {}),
        suggestions=index.get("suggestions", {}),
        duplicate_groups=index.get("duplicate_groups", []),
    )


def _validate_project_root(project_root: str, settings: Settings) -> Path:
    raw = Path(project_root.strip())
    if not str(raw):
        raise ApiError(
            "VALIDATION_ERROR",
            status_code=400,
            detail={"field": "project_root", "reason": "project_root_required"},
        )
    resolved = raw.resolve(strict=False)
    if not resolved.exists() or not resolved.is_dir():
        raise ApiError(
            "VALIDATION_ERROR",
            status_code=400,
            detail={"field": "project_root", "reason": "project_root_must_be_existing_directory"},
        )
    if str(resolved) == resolved.anchor:
        raise ApiError(
            "VALIDATION_ERROR",
            status_code=400,
            detail={"field": "project_root", "reason": "project_root_cannot_be_filesystem_root"},
        )

    allowed_roots = _allowed_import_roots(settings)
    if allowed_roots and not any(_is_relative_to(resolved, root) for root in allowed_roots):
        raise ApiError(
            "VALIDATION_ERROR",
            status_code=400,
            detail={
                "field": "project_root",
                "reason": "project_root_outside_allowed_import_roots",
                "allowedRoots": [str(root) for root in allowed_roots],
            },
        )
    return resolved


def _allowed_import_roots(settings: Settings) -> list[Path]:
    raw_roots = os.environ.get("PHOTO_ASSET_IMPORT_ROOTS", "").strip()
    if raw_roots:
        roots = [
            Path(part).resolve(strict=False)
            for part in raw_roots.split(os.pathsep)
            if part.strip()
        ]
    else:
        roots = [settings.media_root.resolve(strict=False)]
    return [root for root in roots if root.exists()]


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _resolve_asset_index(
    *,
    project_id: str,
    job_id: str | None,
    job_store: JobStore,
    result_store: ResultStore,
):
    if job_id:
        job = job_store.get(job_id)
        if job is None:
            raise ApiError("JOB_NOT_FOUND", status_code=404)
        index = _index_from_job(job.id, result_store)
        if index is None:
            raise ApiError(
                "JOB_NOT_FOUND",
                status_code=404,
                detail={"reason": "asset_index_result_not_found"},
            )
        return job, index

    for job in job_store.list(limit=100):
        if job.type != "asset_indexing":
            continue
        if str(job.context.get("project_id") or "") != project_id:
            continue
        index = _index_from_job(job.id, result_store)
        if index is not None:
            return job, index

    raise ApiError(
        "JOB_NOT_FOUND",
        status_code=404,
        detail={"reason": "project_asset_index_not_found"},
    )


def _index_from_job(job_id: str, result_store: ResultStore) -> dict | None:
    for result in result_store.list_latest_by_job(job_id):
        if result.agent == "asset" and isinstance(result.payload.get("index"), dict):
            return result.payload["index"]
    return None
