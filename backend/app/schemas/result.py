from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.schemas.common import AgentName, ApiSchema, utc_now


AgentResultStatus = Literal["succeeded", "failed", "skipped"]


class AgentResult(ApiSchema):
    id: str
    job_id: str
    agent: AgentName
    status: AgentResultStatus = "succeeded"
    summary: str = ""
    content: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
