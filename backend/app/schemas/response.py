from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.schemas.common import AgentName, ApiSchema, JobStatus, TriggerType
from app.schemas.event import AgentEvent
from app.schemas.job import AgentJob
from app.schemas.media import MediaAsset, MediaStatus
from app.schemas.result import AgentResult, AgentResultStatus


class UploadMediaResponse(ApiSchema):
    media_id: str = Field(alias="mediaId")
    file_name: str = Field(alias="fileName")
    media_type: str = Field(alias="mediaType")
    mime_type: str | None = Field(default=None, alias="mimeType")
    preview_url: str | None = Field(default=None, alias="previewUrl")
    metadata: dict[str, Any] = Field(default_factory=dict)
    size_bytes: int = Field(alias="sizeBytes", ge=0)
    status: MediaStatus = "ready"


class CreateJobResponse(ApiSchema):
    job_id: str = Field(alias="jobId")
    status: JobStatus
    events_url: str = Field(alias="eventsUrl")
    results_url: str = Field(alias="resultsUrl")


class JobDetailResponse(ApiSchema):
    job_id: str = Field(alias="jobId")
    type: str
    trigger: TriggerType = "user"
    status: JobStatus
    agents: list[AgentName] = Field(default_factory=list)
    media_ids: list[str] = Field(default_factory=list, alias="mediaIds")
    progress: float | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    user_goal: str = Field(default="", alias="userGoal")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class AgentResultResponse(ApiSchema):
    agent: AgentName
    status: AgentResultStatus = "succeeded"
    summary: str = ""
    visible_text: str = Field(default="", alias="visibleText")
    structured_payload: dict[str, Any] = Field(default_factory=dict, alias="structuredPayload")
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    created_at: datetime = Field(alias="createdAt")


class JobResultsResponse(ApiSchema):
    job_id: str = Field(alias="jobId")
    status: JobStatus
    results: list[AgentResultResponse] = Field(default_factory=list)
    completed_agents: list[AgentName] = Field(default_factory=list, alias="completedAgents")
    failed_agents: list[AgentName] = Field(default_factory=list, alias="failedAgents")
    pending_agents: list[AgentName] = Field(default_factory=list, alias="pendingAgents")


class JobListResponse(ApiSchema):
    jobs: list[JobDetailResponse] = Field(default_factory=list)
    count: int = 0


class AgentRetryResponse(ApiSchema):
    job_id: str = Field(alias="jobId")
    agent: AgentName
    status: JobStatus
    events_url: str = Field(alias="eventsUrl")
    results_url: str = Field(alias="resultsUrl")


class HandoffResponse(ApiSchema):
    handoff_id: str = Field(alias="handoffId")
    source_agent: AgentName = Field(alias="sourceAgent")
    target_agent: AgentName = Field(alias="targetAgent")
    target_job_id: str | None = Field(default=None, alias="targetJobId")
    status: str = "accepted"


class ErrorResponse(ApiSchema):
    error_code: str = Field(alias="errorCode")
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)


class AgentEventMessage(ApiSchema):
    event_id: str = Field(alias="eventId")
    seq: int
    job_id: str = Field(alias="jobId")
    agent: AgentName | None = None
    type: str
    message: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(alias="createdAt")


def upload_media_response_from_asset(asset: MediaAsset) -> UploadMediaResponse:
    return UploadMediaResponse(
        media_id=asset.id,
        file_name=asset.filename,
        media_type=asset.kind,
        mime_type=asset.content_type,
        preview_url=asset.preview_url,
        metadata=asset.metadata,
        size_bytes=asset.size_bytes,
        status=asset.status,
    )


def create_job_response_from_job(job: AgentJob) -> CreateJobResponse:
    return CreateJobResponse(
        job_id=job.id,
        status=job.status,
        events_url=f"/api/jobs/{job.id}/events",
        results_url=f"/api/jobs/{job.id}/results",
    )


def job_detail_response_from_job(
    job: AgentJob,
    *,
    progress: float | None = None,
) -> JobDetailResponse:
    return JobDetailResponse(
        job_id=job.id,
        type=job.type,
        trigger=job.trigger,
        status=job.status,
        agents=job.agents,
        media_ids=job.media_ids,
        progress=progress,
        context=job.context,
        user_goal=job.user_goal,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def agent_result_response_from_result(result: AgentResult) -> AgentResultResponse:
    warnings = result.payload.get("warnings", [])
    if not isinstance(warnings, list):
        warnings = [str(warnings)]

    return AgentResultResponse(
        agent=result.agent,
        status=result.status,
        summary=result.summary,
        visible_text=result.content,
        structured_payload=result.payload,
        warnings=[str(item) for item in warnings],
        error=result.error,
        created_at=result.created_at,
    )


def job_results_response_from_job(
    job: AgentJob,
    results: list[AgentResult],
) -> JobResultsResponse:
    result_by_agent = {result.agent: result for result in results}
    return JobResultsResponse(
        job_id=job.id,
        status=job.status,
        results=[agent_result_response_from_result(result) for result in results],
        completed_agents=[
            agent
            for agent in job.agents
            if result_by_agent.get(agent) and result_by_agent[agent].status == "succeeded"
        ],
        failed_agents=[
            agent
            for agent in job.agents
            if result_by_agent.get(agent) and result_by_agent[agent].status == "failed"
        ],
        pending_agents=[
            agent
            for agent in job.agents
            if agent not in result_by_agent
        ],
    )


def job_list_response_from_jobs(jobs: list[AgentJob]) -> JobListResponse:
    return JobListResponse(
        jobs=[job_detail_response_from_job(job) for job in jobs],
        count=len(jobs),
    )


def agent_retry_response_from_job(job: AgentJob, agent: AgentName) -> AgentRetryResponse:
    return AgentRetryResponse(
        job_id=job.id,
        agent=agent,
        status=job.status,
        events_url=f"/api/jobs/{job.id}/events",
        results_url=f"/api/jobs/{job.id}/results",
    )


def agent_event_message_from_event(event: AgentEvent) -> AgentEventMessage:
    return AgentEventMessage(
        event_id=event.id,
        seq=event.seq,
        job_id=event.job_id,
        agent=event.agent,
        type=event.type,
        message=event.message,
        payload=event.payload,
        created_at=event.created_at,
    )
