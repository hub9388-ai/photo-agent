from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.core.errors import ApiError
from app.schemas.response import ErrorResponse, UploadMediaResponse
from app.storage.media_store import (
    MediaProcessingError,
    MediaStore,
    MediaStoreError,
    MediaTooLargeError,
    UnsupportedMediaTypeError,
    get_media_store,
)

router = APIRouter(prefix="/api/media", tags=["media"])


@router.post(
    "/upload",
    response_model=UploadMediaResponse,
    status_code=201,
    summary="Upload media and prepare model preview",
    responses={
        413: {"model": ErrorResponse, "description": "Media too large"},
        415: {"model": ErrorResponse, "description": "Unsupported media type"},
    },
)
async def upload_media(
    file: UploadFile = File(...),
    media_store: MediaStore = Depends(get_media_store),
) -> UploadMediaResponse:
    try:
        return await run_in_threadpool(media_store.save_and_prepare_sync, file)
    except UnsupportedMediaTypeError as exc:
        raise ApiError(
            "MEDIA_INVALID_TYPE",
            status_code=exc.status_code,
            detail={"reason": str(exc)},
        ) from exc
    except MediaTooLargeError as exc:
        raise ApiError(
            "MEDIA_TOO_LARGE",
            status_code=exc.status_code,
            detail={"reason": str(exc)},
        ) from exc
    except MediaProcessingError as exc:
        raise ApiError(
            "MEDIA_PROCESSING_FAILED",
            status_code=exc.status_code,
            detail={"reason": str(exc)},
        ) from exc
    except MediaStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
