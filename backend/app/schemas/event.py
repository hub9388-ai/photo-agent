from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import AgentName, ApiSchema, EventType, utc_now


class AgentEvent(ApiSchema):
    id: str
    job_id: str
    seq: int = Field(ge=1)
    agent: AgentName | None
    type: EventType
    message: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    persist: bool = True
    created_at: datetime = Field(default_factory=utc_now)


PERSISTED_EVENT_TYPES = frozenset(
    {
        "job.created",
        "job.started",
        "agent.started",
        "agent.result",
        "agent.error",
        "job.completed",
        "job.partial_completed",
        "job.failed",
    }
)
STREAM_ONLY_EVENT_TYPES = frozenset({"agent.delta"})


def should_persist_event(
    event: AgentEvent,
    *,
    previous_progress_step: str | None = None,
) -> bool:
    if not event.persist:
        return False
    if event.type in STREAM_ONLY_EVENT_TYPES:
        return False
    if event.type == "agent.progress":
        step = event.payload.get("step")
        return isinstance(step, str) and bool(step) and step != previous_progress_step
    return event.type in PERSISTED_EVENT_TYPES
