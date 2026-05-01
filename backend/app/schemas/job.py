from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import AgentName, ApiSchema, JobStatus, JobType, TriggerType, utc_now


class AgentJob(ApiSchema):
    id: str
    type: JobType
    trigger: TriggerType = "user"
    media_ids: list[str] = Field(default_factory=list)
    agents: list[AgentName] = Field(min_length=1)
    status: JobStatus
    user_goal: str = ""
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CreateJobRequest(ApiSchema):
    type: JobType = "photo_review"
    trigger: TriggerType = "user"
    media_ids: list[str] = Field(default_factory=list)
    agents: list[AgentName] = Field(default_factory=lambda: ["post", "coach"], min_length=1)
    user_goal: str = ""
    context: dict[str, Any] = Field(default_factory=dict)


class JobResponse(ApiSchema):
    job: AgentJob
