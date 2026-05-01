from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import AgentName, ApiSchema, TriggerType, utc_now


class HandoffRequest(ApiSchema):
    source_job_id: str
    source_agent: AgentName
    target_agent: AgentName
    media_ids: list[str] = Field(default_factory=list)
    user_goal: str = ""
    trigger: TriggerType = "handoff"
    context: dict[str, Any] = Field(default_factory=dict)


class HandoffResponse(ApiSchema):
    handoff_id: str
    source_job_id: str
    target_job_id: str | None = None
    source_agent: AgentName
    target_agent: AgentName
    status: str = "accepted"
    created_at: datetime = Field(default_factory=utc_now)
