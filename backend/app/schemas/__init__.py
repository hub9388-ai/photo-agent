"""Pydantic schemas shared by the API, orchestration layer, and tests."""

from app.schemas.agent import (
    AgentRequest,
    AssetAgentRequest,
    BaseAgentRequest,
    CoachAgentRequest,
    PlanAgentRequest,
    PostAgentRequest,
)
from app.schemas.event import AgentEvent
from app.schemas.handoff import HandoffRequest
from app.schemas.job import AgentJob
from app.schemas.media import MediaAsset
from app.schemas.result import AgentResult
from app.schemas.response import (
    AgentEventMessage,
    AgentResultResponse,
    CreateJobResponse,
    ErrorResponse,
    HandoffResponse,
    JobDetailResponse,
    JobResultsResponse,
    UploadMediaResponse,
)

__all__ = [
    "AgentEvent",
    "AgentJob",
    "AgentRequest",
    "AgentResult",
    "AgentEventMessage",
    "AgentResultResponse",
    "AssetAgentRequest",
    "BaseAgentRequest",
    "CoachAgentRequest",
    "CreateJobResponse",
    "ErrorResponse",
    "HandoffRequest",
    "HandoffResponse",
    "JobDetailResponse",
    "JobResultsResponse",
    "MediaAsset",
    "PlanAgentRequest",
    "PostAgentRequest",
    "UploadMediaResponse",
]
