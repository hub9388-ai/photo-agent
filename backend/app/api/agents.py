from __future__ import annotations

from fastapi import APIRouter, Depends

from app.agents.asset_agent import AssetAgentService, get_asset_agent_service
from app.core.errors import ApiError
from app.orchestration.event_bus import EventBus, get_event_bus
from app.orchestration.job_runner import JobRunner, get_job_runner
from app.schemas.event import AgentEvent
from app.schemas.asset_score import AssetScoreRequest, AssetScoreResponse
from app.schemas.job import CreateJobRequest
from app.schemas.plan import PlanRunRequest, PlanRunResponse
from app.schemas.response import ErrorResponse, create_job_response_from_job
from app.storage.event_store import EventStore, get_event_store
from app.storage.job_store import JobStore, get_job_store
from app.storage.media_store import MediaNotFoundError, MediaStore, MediaStoreError, get_media_store

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.post(
    "/plan/run",
    response_model=PlanRunResponse,
    status_code=202,
    summary="Run the planning agent explicitly",
    responses={
        400: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def run_plan_agent(
    request: PlanRunRequest,
    job_store: JobStore = Depends(get_job_store),
    event_store: EventStore = Depends(get_event_store),
    event_bus: EventBus = Depends(get_event_bus),
    job_runner: JobRunner = Depends(get_job_runner),
    media_store: MediaStore = Depends(get_media_store),
) -> PlanRunResponse:
    _validate_reference_media(request.reference_media_ids, media_store)
    context = _build_plan_context(request)
    create_request = CreateJobRequest(
        type="trip_planning",
        trigger=request.trigger,
        media_ids=request.reference_media_ids,
        agents=["plan"],
        user_goal=request.user_goal,
        context=context,
    )
    job = job_store.create_from_request(create_request)
    event = AgentEvent(
        id=f"evt_{job.id}_created",
        job_id=job.id,
        seq=event_store.next_seq(job.id),
        agent=None,
        type="job.created",
        message="拍摄规划任务已创建",
        payload={"agents": job.agents, "referenceMediaIds": request.reference_media_ids},
    )
    event_store.append_if_persisted(event)
    await event_bus.publish(event)
    job_runner.start(job.id)
    base_response = create_job_response_from_job(job)
    return PlanRunResponse(**base_response.model_dump())


@router.post(
    "/asset/score",
    response_model=AssetScoreResponse,
    summary="Score uploaded media with the AssetAgent visual pipeline",
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def score_uploaded_assets(
    request: AssetScoreRequest,
    media_store: MediaStore = Depends(get_media_store),
    asset_agent: AssetAgentService = Depends(get_asset_agent_service),
) -> AssetScoreResponse:
    try:
        return await asset_agent.score_uploaded_media(
            request.media_ids,
            media_store,
            culling_preference=request.culling_preference,
        )
    except MediaNotFoundError as exc:
        raise ApiError(
            "VALIDATION_ERROR",
            status_code=404,
            detail={"reason": str(exc), "mediaIds": request.media_ids},
        ) from exc
    except MediaStoreError as exc:
        raise ApiError(
            "MEDIA_PROCESSING_FAILED",
            status_code=exc.status_code,
            detail={"reason": str(exc)},
        ) from exc


def _build_plan_context(request: PlanRunRequest) -> dict:
    context = dict(request.context)
    context.update(
        {
            "user_id": request.user_id,
            "project_id": request.project_id,
            "city": request.city,
            "target_location": request.target_location,
            "shoot_date": request.shoot_date,
            "time_window": request.time_window,
            "subject": request.subject,
            "budget": request.budget,
            "constraints": request.constraints,
            "style_keywords": request.style_keywords,
            "gear": request.gear,
            "reference_media_ids": request.reference_media_ids,
        }
    )
    return {key: value for key, value in context.items() if value not in (None, "", [])}


def _validate_reference_media(media_ids: list[str], media_store: MediaStore) -> None:
    missing_media_ids: list[str] = []
    for media_id in media_ids:
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
                "field": "reference_media_ids",
                "missingMediaIds": missing_media_ids,
            },
        )
