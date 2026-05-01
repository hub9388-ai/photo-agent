from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from app.schemas.common import ApiSchema, TriggerType
from app.schemas.response import CreateJobResponse


class PlanRunRequest(ApiSchema):
    user_goal: str = ""
    trigger: TriggerType = "user"
    user_id: str | None = None
    project_id: str | None = None
    city: str | None = None
    target_location: str | None = None
    shoot_date: str | None = None
    time_window: str | None = None
    subject: str | None = None
    budget: str | None = None
    constraints: list[str] = Field(default_factory=list)
    style_keywords: list[str] = Field(default_factory=list)
    gear: list[str] = Field(default_factory=list)
    reference_media_ids: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


class PlanRunResponse(CreateJobResponse):
    agent: Literal["plan"] = "plan"
