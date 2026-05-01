from __future__ import annotations

from fastapi import APIRouter, Depends

from app.orchestration.event_bus import EventBus, get_event_bus
from app.orchestration.handoff_service import HandoffService
from app.orchestration.job_runner import JobRunner, get_job_runner
from app.schemas.handoff import HandoffRequest
from app.schemas.response import ErrorResponse, HandoffResponse
from app.storage.event_store import EventStore, get_event_store
from app.storage.job_store import JobStore, get_job_store
from app.storage.media_store import MediaStore, get_media_store
from app.storage.result_store import ResultStore, get_result_store

router = APIRouter(prefix="/api/handoff", tags=["handoff"])


@router.post(
    "",
    response_model=HandoffResponse,
    status_code=202,
    summary="Create an agent handoff",
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        501: {"model": ErrorResponse},
    },
)
async def create_handoff(
    request: HandoffRequest,
    job_store: JobStore = Depends(get_job_store),
    result_store: ResultStore = Depends(get_result_store),
    event_store: EventStore = Depends(get_event_store),
    event_bus: EventBus = Depends(get_event_bus),
    job_runner: JobRunner = Depends(get_job_runner),
    media_store: MediaStore = Depends(get_media_store),
) -> HandoffResponse:
    service = HandoffService(
        job_store=job_store,
        result_store=result_store,
        event_store=event_store,
        event_bus=event_bus,
        job_runner=job_runner,
        media_store=media_store,
    )
    return await service.create_handoff(request)
