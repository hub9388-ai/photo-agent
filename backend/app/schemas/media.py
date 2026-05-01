from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.schemas.common import ApiSchema, utc_now


MediaKind = Literal["photo", "video", "raw", "other"]
MediaStatus = Literal["uploaded", "processing", "ready", "failed"]


class MediaAsset(ApiSchema):
    id: str
    user_id: str | None = None
    project_id: str | None = None
    kind: MediaKind
    filename: str
    content_type: str | None = None
    size_bytes: int = Field(ge=0)
    storage_uri: str
    preview_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: MediaStatus = "uploaded"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
