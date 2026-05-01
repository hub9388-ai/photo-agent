from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.schemas.common import ApiSchema


AssetGrade = Literal["A", "B", "C", "reject", "duplicate", "unscored"]


class AssetScoreRequest(ApiSchema):
    media_ids: list[str] = Field(alias="mediaIds", min_length=1)
    culling_preference: Literal["conservative", "balanced", "aggressive"] = Field(
        default="balanced",
        alias="cullingPreference",
    )
    context: dict[str, Any] = Field(default_factory=dict)


class ScoredAssetMetadata(ApiSchema):
    iso: str | None = None
    aperture: str | None = None
    shutter: str | None = None
    focal_length: str | None = Field(default=None, alias="focalLength")
    camera: str | None = None
    captured_at: str | None = Field(default=None, alias="capturedAt")
    width: int | None = None
    height: int | None = None
    location: str | None = None
    file_size: str | None = Field(default=None, alias="fileSize")
    brightness: float | None = None
    sharpness: float | None = None
    contrast: float | None = None
    colorfulness: float | None = None
    visual_status: str | None = Field(default=None, alias="visualStatus")


class ScoredAsset(ApiSchema):
    asset_id: str = Field(alias="assetId")
    media_id: str = Field(alias="mediaId")
    file_name: str = Field(alias="fileName")
    preview_url: str | None = Field(default=None, alias="previewUrl")
    mime_type: str | None = Field(default=None, alias="mimeType")
    media_category: str = Field(default="image", alias="mediaCategory")
    metadata: ScoredAssetMetadata = Field(default_factory=ScoredAssetMetadata)
    grade: AssetGrade
    score: float | None = None
    tags: list[str] = Field(default_factory=list)
    ai_reasons: list[str] = Field(default_factory=list, alias="aiReasons")
    issues: list[str] = Field(default_factory=list)
    duplicate_group_id: str | None = Field(default=None, alias="duplicateGroupId")
    duplicate_of: str | None = Field(default=None, alias="duplicateOf")
    upload_status: str = Field(default="uploaded", alias="uploadStatus")
    error_message: str | None = Field(default=None, alias="errorMessage")
    created_at: datetime | None = Field(default=None, alias="createdAt")


class AssetScoreResponse(ApiSchema):
    assets: list[ScoredAsset] = Field(default_factory=list)
    duplicate_groups: list[dict[str, Any]] = Field(default_factory=list, alias="duplicateGroups")
    scoring_method: str = Field(default="asset_agent", alias="scoringMethod")
    warnings: list[str] = Field(default_factory=list)
