from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.response import ErrorResponse


ERROR_MESSAGES = {
    "MEDIA_INVALID_TYPE": "Unsupported media type.",
    "MEDIA_TOO_LARGE": "Uploaded media is too large.",
    "MEDIA_PROCESSING_FAILED": "Media processing failed.",
    "MODEL_TIMEOUT": "Model request timed out.",
    "MODEL_RATE_LIMIT": "Model is busy. Please retry later.",
    "MODEL_AUTH_FAILED": "服务暂时不可用，请稍后重试。",
    "AGENT_FAILED": "Agent execution failed.",
    "JOB_NOT_FOUND": "Job not found.",
    "PROVIDER_UNAVAILABLE": "Provider is unavailable.",
    "HANDOFF_REJECTED": "Handoff request was rejected.",
    "VALIDATION_ERROR": "Request validation failed.",
}


class ApiError(Exception):
    def __init__(
        self,
        error_code: str,
        *,
        status_code: int = 400,
        message: str | None = None,
        detail: dict[str, Any] | None = None,
        debug: dict[str, Any] | None = None,
    ) -> None:
        self.error_code = error_code
        self.status_code = status_code
        self.message = message or ERROR_MESSAGES.get(error_code, "Request failed.")
        self.detail = detail or {}
        self.debug = debug or {}
        super().__init__(self.message)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(exc.error_code, exc.message, exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_error_payload(
                "VALIDATION_ERROR",
                ERROR_MESSAGES["VALIDATION_ERROR"],
                {"errors": _compact_validation_errors(exc.errors())},
            ),
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(_request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict):
            detail = dict(exc.detail)
            error_code = str(detail.pop("errorCode", detail.pop("error_code", "")) or "VALIDATION_ERROR")
            message = str(detail.pop("message", ERROR_MESSAGES.get(error_code, "Request failed.")))
            return JSONResponse(
                status_code=exc.status_code,
                content=_error_payload(error_code, message, detail),
            )

        error_code = "JOB_NOT_FOUND" if exc.status_code == 404 else "VALIDATION_ERROR"
        message = str(exc.detail or ERROR_MESSAGES.get(error_code, "Request failed."))
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(error_code, message, {}),
        )


def _error_payload(error_code: str, message: str, detail: dict[str, Any]) -> dict[str, Any]:
    return ErrorResponse(
        error_code=error_code,
        message=message,
        detail=detail,
    ).model_dump(mode="json", by_alias=True)


def _compact_validation_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for error in errors:
        compact.append(
            {
                "type": error.get("type"),
                "loc": error.get("loc"),
                "msg": error.get("msg"),
            }
        )
    return compact
