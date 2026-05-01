from __future__ import annotations

from typing import Any

from pydantic import Field

from app.schemas.common import ApiSchema, JobStatus


class AssetImportRequest(ApiSchema):
    project_root: str = Field(alias="projectRoot")
    project_name: str = Field(default="", alias="projectName")
    culling_preference: str = Field(default="", alias="cullingPreference")
    user_goal: str = Field(default="", alias="userGoal")
    context: dict[str, Any] = Field(default_factory=dict)


class AssetImportResponse(ApiSchema):
    project_id: str = Field(alias="projectId")
    job_id: str = Field(alias="jobId")
    status: JobStatus
    events_url: str = Field(alias="eventsUrl")
    results_url: str = Field(alias="resultsUrl")


class ProjectAssetSummary(ApiSchema):
    asset_id: str = Field(alias="assetId")
    relative_path: str = Field(alias="relativePath")
    absolute_path: str = Field(alias="absolutePath")
    delivery_grade: str = Field(default="", alias="deliveryGrade")
    quality_score: float | None = Field(default=None, alias="qualityScore")
    scene_id: str = Field(default="", alias="sceneId")
    burst_id: str = Field(default="", alias="burstId")
    duplicate_group: str = Field(default="", alias="duplicateGroup")
    duplicate_of: str = Field(default="", alias="duplicateOf")
    reject_reasons: list[str] = Field(default_factory=list, alias="rejectReasons")
    tags: list[str] = Field(default_factory=list)


class ProjectAssetsResponse(ApiSchema):
    project_id: str = Field(alias="projectId")
    job_id: str = Field(alias="jobId")
    status: JobStatus
    assets: list[ProjectAssetSummary] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)
    suggestions: dict[str, Any] = Field(default_factory=dict)
    duplicate_groups: list[dict[str, Any]] = Field(default_factory=list, alias="duplicateGroups")


def asset_import_response_from_job(project_id: str, job_id: str, status: JobStatus) -> AssetImportResponse:
    return AssetImportResponse(
        project_id=project_id,
        job_id=job_id,
        status=status,
        events_url=f"/api/jobs/{job_id}/events",
        results_url=f"/api/jobs/{job_id}/results",
    )


def project_asset_summary_from_record(asset: dict[str, Any]) -> ProjectAssetSummary:
    return ProjectAssetSummary(
        asset_id=str(asset.get("id", "")),
        relative_path=str(asset.get("relative_path", "")),
        absolute_path=str(asset.get("absolute_path", "")),
        delivery_grade=str(asset.get("delivery_grade", "")),
        quality_score=asset.get("quality_score"),
        scene_id=str(asset.get("scene_id", "")),
        burst_id=str(asset.get("burst_id", "")),
        duplicate_group=str(asset.get("duplicate_group", "")),
        duplicate_of=str(asset.get("duplicate_of", "")),
        reject_reasons=[str(item) for item in asset.get("reject_reasons", [])],
        tags=[str(item) for item in asset.get("tags", [])],
    )
