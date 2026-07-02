"""Global exception handlers that translate domain errors into HTTP responses.

Keeping this translation in one place means services and repositories never
need to know about HTTP status codes, which preserves clean architecture
boundaries between layers.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.rbac import InsufficientRoleError

logger = get_logger(__name__)

_STATUS_MAP = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ValidationError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ConflictError: status.HTTP_409_CONFLICT,
    ServiceUnavailableError: status.HTTP_503_SERVICE_UNAVAILABLE,
    InsufficientRoleError: status.HTTP_403_FORBIDDEN,
}


def register_error_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app.

    Args:
        app: The FastAPI application instance to attach handlers to.
    """

    for exc_class, http_status in _STATUS_MAP.items():

        def _make_handler(status_code: int):
            async def _handler(request: Request, exc: Exception) -> JSONResponse:
                logger.warning(
                    "Handled domain error: %s | path=%s | detail=%s",
                    type(exc).__name__,
                    request.url.path,
                    str(exc),
                )
                return JSONResponse(
                    status_code=status_code,
                    content={"error": type(exc).__name__, "detail": str(exc)},
                )

            return _handler

        app.add_exception_handler(exc_class, _make_handler(http_status))

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all handler for unexpected exceptions.

        Never leaks internal stack traces to clients; full details are logged
        server-side only.
        """
        logger.error(
            "Unhandled exception on path=%s: %s", request.url.path, str(exc), exc_info=True
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "InternalServerError", "detail": "An unexpected error occurred."},
        )
