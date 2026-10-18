from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse

from app.core.errors import ApiError
from app.orchestration.event_bus import EventBus, get_event_bus
from app.orchestration.job_runner import JobRunner, get_job_runner
from app.schemas.common import AgentName
from app.schemas.event import AgentEvent
from app.schemas.job import CreateJobRequest
from app.schemas.response import (
    AgentRetryResponse,
    CreateJobResponse,
    ErrorResponse,
    JobDetailResponse,
    JobListResponse,
    JobResultsResponse,
    agent_event_message_from_event,
    agent_retry_response_from_job,
    create_job_response_from_job,
    job_detail_response_from_job,
    job_list_response_from_jobs,
    job_results_response_from_job,
)
from app.storage.event_store import EventStore, get_event_store
from app.storage.job_store import JobStore, get_job_store
from app.storage.media_store import MediaNotFoundError, MediaStore, MediaStoreError, get_media_store
from app.storage.result_store import ResultStore, get_result_store

router = APIRouter(prefix="/api/jobs", tags=["jobs"])
MEDIA_REQUIRED_AGENTS = frozenset({"post", "coach"})


@router.get("/{job_id}/retouch-advice", summary="Convert saved Post advice to an unapplied slider draft")
def get_retouch_advice(
    job_id: str,
    media_id: str,
    job_store: JobStore = Depends(get_job_store),
    result_store: ResultStore = Depends(get_result_store),
) -> dict:
    from app.orchestration.retouch_advice import convert_post_advice

    job = job_store.get(job_id)
    if job is None:
        raise ApiError("JOB_NOT_FOUND", status_code=404)
    # Do not attach another photo's advice, or guess ownership in batch analysis.
    if job.media_ids != [media_id]:
        raise ApiError("VALIDATION_ERROR", status_code=400, detail={"reason": "single_photo_job_media_mismatch"})
    post = next((r for r in result_store.list_latest_by_job(job_id) if r.agent == "post"), None)
    if post is None or post.status != "succeeded":
        raise ApiError("VALIDATION_ERROR", status_code=409, detail={"reason": "post_result_not_ready"})
    source = post.payload.get("xmp_params", post.payload.get("xmpParams"))
    if not isinstance(source, dict) or not source or len(source) > 100:
        raise ApiError("VALIDATION_ERROR", status_code=422, detail={"reason": "structured_post_parameters_required"})
    return convert_post_advice(source, job_id=job_id, media_id=media_id, result_id=post.id)


@router.post(
    "",
    response_model=CreateJobResponse,
    status_code=202,
    summary="Create an agent job",
    responses={
        400: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def create_job(
    request: CreateJobRequest,
    job_store: JobStore = Depends(get_job_store),
    event_store: EventStore = Depends(get_event_store),
    event_bus: EventBus = Depends(get_event_bus),
    job_runner: JobRunner = Depends(get_job_runner),
    media_store: MediaStore = Depends(get_media_store),
) -> CreateJobResponse:
    _validate_job_media(request, media_store)
    job = job_store.create_from_request(request)
    event = AgentEvent(
        id=f"evt_{job.id}_created",
        job_id=job.id,
        seq=event_store.next_seq(job.id),
        agent=None,
        type="job.created",
        message="任务已创建",
        payload={"agents": job.agents, "mediaIds": job.media_ids},
    )
    event_store.append_if_persisted(event)
    await event_bus.publish(event)
    job_runner.start(job.id)
    return create_job_response_from_job(job)


def _validate_job_media(request: CreateJobRequest, media_store: MediaStore) -> None:
    requires_media = any(agent in MEDIA_REQUIRED_AGENTS for agent in request.agents)
    if requires_media and not request.media_ids:
        raise ApiError(
            "VALIDATION_ERROR",
            status_code=400,
            detail={
                "field": "media_ids",
                "reason": "media_ids_required_for_post_or_coach",
            },
        )

    missing_media_ids: list[str] = []
    for media_id in request.media_ids:
        try:
            media_store.get(media_id)
        except MediaNotFoundError:
            missing_media_ids.append(media_id)
        except MediaStoreError as exc:
            raise ApiError(
                "MEDIA_PROCESSING_FAILED",
                status_code=exc.status_code,
                detail={"mediaId": media_id, "reason": str(exc)},
            ) from exc

    if missing_media_ids:
        raise ApiError(
            "VALIDATION_ERROR",
            status_code=400,
            detail={
                "field": "media_ids",
                "missingMediaIds": missing_media_ids,
            },
        )


@router.get(
    "",
    response_model=JobListResponse,
    summary="List jobs, optionally filtered by media id",
    responses={422: {"model": ErrorResponse}},
)
def list_jobs(
    media_id: str | None = None,
    limit: int = 50,
    job_store: JobStore = Depends(get_job_store),
) -> JobListResponse:
    normalized_limit = min(max(limit, 1), 100)
    return job_list_response_from_jobs(
        job_store.list(media_id=media_id, limit=normalized_limit)
    )


@router.get(
    "/{job_id}",
    response_model=JobDetailResponse,
    summary="Get job detail",
    responses={404: {"model": ErrorResponse}},
)
def get_job(
    job_id: str,
    job_store: JobStore = Depends(get_job_store),
) -> JobDetailResponse:
    job = job_store.get(job_id)
    if job is None:
        raise ApiError("JOB_NOT_FOUND", status_code=404)
    return job_detail_response_from_job(job)


@router.get(
    "/{job_id}/events",
    summary="Stream or replay job events",
    responses={
        200: {"content": {"text/event-stream": {}}},
        404: {"model": ErrorResponse},
    },
)
async def get_job_events(
    job_id: str,
    request: Request,
    after_seq: int = 0,
    replay_only: bool = False,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    job_store: JobStore = Depends(get_job_store),
    event_store: EventStore = Depends(get_event_store),
    event_bus: EventBus = Depends(get_event_bus),
) -> StreamingResponse:
    if job_store.get(job_id) is None:
        raise ApiError("JOB_NOT_FOUND", status_code=404)

    replay_after = _resolve_replay_after(after_seq, last_event_id)

    async def event_stream():
        for event in event_store.list_by_job(job_id, after_seq=replay_after):
            yield _format_sse_event(event)

        if replay_only:
            return

        async with event_bus.subscribe(job_id) as queue:
            while not await request.is_disconnected():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield _format_sse_event(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get(
    "/{job_id}/results",
    response_model=JobResultsResponse,
    summary="Get job results",
    responses={404: {"model": ErrorResponse}},
)
def get_job_results(
    job_id: str,
    job_store: JobStore = Depends(get_job_store),
    result_store: ResultStore = Depends(get_result_store),
) -> JobResultsResponse:
    job = job_store.get(job_id)
    if job is None:
        raise ApiError("JOB_NOT_FOUND", status_code=404)
    return job_results_response_from_job(job, result_store.list_latest_by_job(job_id))


@router.post(
    "/{job_id}/agents/{agent}/retry",
    response_model=AgentRetryResponse,
    status_code=202,
    summary="Retry one agent for an existing job",
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def retry_agent(
    job_id: str,
    agent: AgentName,
    job_store: JobStore = Depends(get_job_store),
    job_runner: JobRunner = Depends(get_job_runner),
) -> AgentRetryResponse:
    job = job_store.get(job_id)
    if job is None:
        raise ApiError("JOB_NOT_FOUND", status_code=404)
    if agent not in job.agents:
        raise ApiError(
            "VALIDATION_ERROR",
            status_code=400,
            detail={"agent": agent, "allowedAgents": job.agents},
        )
    if agent not in {"post", "coach"}:
        raise ApiError(
            "AGENT_FAILED",
            status_code=400,
            detail={"agent": agent, "reason": "retry_not_supported_for_agent"},
        )

    job_runner.start_agent_retry(job.id, agent)
    refreshed = job_store.get(job.id) or job
    return agent_retry_response_from_job(refreshed, agent)


def _resolve_replay_after(after_seq: int, last_event_id: str | None) -> int:
    if last_event_id:
        try:
            return max(after_seq, int(last_event_id))
        except ValueError:
            return after_seq
    return after_seq


def _format_sse_event(event: AgentEvent) -> str:
    event_message = agent_event_message_from_event(event)
    data = json.dumps(event_message.model_dump(mode="json", by_alias=True), ensure_ascii=False)
    return f"id: {event.seq}\nevent: {event.type}\ndata: {data}\n\n"
