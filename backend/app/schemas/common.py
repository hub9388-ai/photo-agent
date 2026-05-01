from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict


AgentName: TypeAlias = Literal["post", "coach", "plan", "asset"]
TriggerType: TypeAlias = Literal["user", "handoff", "system", "retry"]
JobType: TypeAlias = Literal[
    "photo_review",
    "post_process_advice",
    "coach_feedback",
    "asset_indexing",
    "trip_planning",
    "batch_review",
]
JobStatus: TypeAlias = Literal[
    "queued",
    "running",
    "streaming",
    "completed",
    "partial_completed",
    "failed",
    "cancelled",
]
EventType: TypeAlias = Literal[
    "job.created",
    "job.started",
    "agent.started",
    "agent.progress",
    "agent.delta",
    "agent.result",
    "agent.error",
    "job.completed",
    "job.partial_completed",
    "job.failed",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ApiSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
