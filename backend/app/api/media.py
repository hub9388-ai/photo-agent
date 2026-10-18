from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Path as PathParam
from fastapi.responses import FileResponse
from PIL import Image
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


@router.get("/{media_id}", response_model=UploadMediaResponse)
async def get_media(
    media_id: Annotated[str, PathParam(pattern=r"^media_[A-Za-z0-9_-]+$")],
    media_store: MediaStore = Depends(get_media_store),
) -> UploadMediaResponse:
    try:
        asset = await run_in_threadpool(media_store.get, media_id)
        return media_store.to_upload_response(asset)
    except MediaStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/{media_id}/retouch-source", summary="Export a stored photo to the retouch editor")
def retouch_source(
    media_id: Annotated[str, PathParam(pattern=r"^media_[A-Za-z0-9_-]+$", max_length=100)],
    media_store: MediaStore = Depends(get_media_store),
) -> FileResponse:
    try:
        asset = media_store.get(media_id)
    except MediaStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    root = media_store.root.resolve()
    original = Path(asset.storage_uri).resolve()
    preview = (media_store.previews_dir / f"{media_id}.jpg").resolve()
    mime_by_format = {"JPEG": ("image/jpeg", "jpg"), "PNG": ("image/png", "png"), "WEBP": ("image/webp", "webp")}
    for path, source in ((original, "original"), (preview, "preview")):
        if not path.is_relative_to(root) or not path.is_file():
            continue
        try:
            with Image.open(path) as image:
                mime = mime_by_format.get(image.format or "")
        except (OSError, ValueError):
            continue
        if mime is None:
            continue
        if path.stat().st_size > 20 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Retouch import is limited to 20 MB; choose a smaller image.")
        filename = f"{media_id}.{mime[1]}"
        return FileResponse(path, media_type=mime[0], filename=filename, headers={
            "X-Retouch-Source": source,
            "X-Retouch-Filename": filename,
            "Access-Control-Expose-Headers": "X-Retouch-Source, X-Retouch-Filename",
            "Cache-Control": "no-store",
        })
    raise HTTPException(status_code=404, detail="No supported image found inside the media directory.")


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
