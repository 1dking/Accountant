import logging
import traceback
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code


class NotFoundError(AppError):
    def __init__(self, resource: str, resource_id: str):
        super().__init__(
            code=f"{resource.upper()}_NOT_FOUND",
            message=f"{resource} with ID {resource_id} was not found.",
            status_code=404,
        )


class ConflictError(AppError):
    def __init__(self, message: str):
        super().__init__(code="CONFLICT", message=message, status_code=409)


class ForbiddenError(AppError):
    def __init__(self, message: str = "You do not have permission to perform this action."):
        super().__init__(code="FORBIDDEN", message=message, status_code=403)


class RateLimitError(AppError):
    def __init__(self, message: str = "Too many requests. Please try again later."):
        super().__init__(code="RATE_LIMITED", message=message, status_code=429)


class ValidationError(AppError):
    def __init__(self, message: str):
        super().__init__(code="VALIDATION_ERROR", message=message, status_code=422)


def _extract_user_id(request: Request) -> uuid.UUID | None:
    """Try to extract user_id from the request's auth token without raising."""
    try:
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            return None
        from app.auth.utils import decode_token
        token_data = decode_token(auth[7:])
        return token_data.sub if token_data else None
    except Exception:
        return None


async def _log_error_to_db(
    request: Request,
    error_type: str,
    message: str,
    tb: str | None = None,
    level: str = "error",
) -> None:
    """Persist an error to the error_logs table. Fire-and-forget — never raises."""
    try:
        session_factory = request.app.state.session_factory
        async with session_factory() as db:
            from app.platform_admin.models import ErrorLog
            user_id = _extract_user_id(request)
            error = ErrorLog(
                id=uuid.uuid4(),
                level=level,
                source=error_type,
                message=message[:2000],
                traceback=tb[:10000] if tb else None,
                user_id=user_id,
                request_path=request.url.path,
                request_method=request.method,
            )
            db.add(error)
            await db.commit()
    except Exception:
        logger.warning("Failed to persist error log to DB", exc_info=True)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": None,
                }
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": "HTTP_ERROR",
                    "message": exc.detail,
                    "details": None,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        tb_str = "".join(tb)
        error_type = type(exc).__name__
        error_message = str(exc) or "Unknown error"

        logger.exception("Unhandled %s on %s %s", error_type, request.method, request.url.path)

        # Persist to error_logs table
        await _log_error_to_db(
            request,
            error_type=error_type,
            message=error_message,
            tb=tb_str,
            level="error",
        )

        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": error_type,
                    "message": error_message[:500],
                    "details": tb_str[:500] if tb_str else None,
                }
            },
        )
