"""EnterpriseGPT FastAPI application entrypoint.

Responsible for application startup wiring only: middleware, routers,
exception handlers, and lifecycle hooks. Business logic must never live
in this file.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.error_handlers import register_error_handlers
from app.core.logging import configure_logging, get_logger
from app.infrastructure.storage.minio_client import ensure_default_bucket

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown events.

    On startup, ensures the default MinIO bucket exists. On shutdown, logs
    a clean termination message. Database and Redis connections are lazy
    (created on first use) and pooled, so no explicit setup is required here.

    Args:
        app: The FastAPI application instance.

    Yields:
        Control back to FastAPI while the application serves requests.
    """
    settings = get_settings()
    logger.info("Starting %s (env=%s)", settings.project_name, settings.environment)
    try:
        ensure_default_bucket()
    except Exception:
        # Storage may not be reachable in some local/dev workflows; readiness
        # probe will surface this rather than crashing the whole app on boot.
        logger.warning("Could not verify MinIO bucket at startup; will retry on demand")
    yield
    logger.info("Shutting down %s", settings.project_name)


def create_app() -> FastAPI:
    """Application factory.

    Returns:
        A fully configured `FastAPI` instance.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.project_name,
        description="Enterprise AI Knowledge Platform — RAG over your organization's documents.",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
