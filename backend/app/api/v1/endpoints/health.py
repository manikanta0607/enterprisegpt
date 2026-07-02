"""Health check endpoints.

Provides Kubernetes-style liveness and readiness probes:
- `/health/live`: is the process running at all?
- `/health/ready`: are the process AND its dependencies (DB, cache, storage) ready?
"""

from fastapi import APIRouter

from app import __version__
from app.core.config import get_settings
from app.infrastructure.cache.redis_client import check_redis_connection
from app.infrastructure.database.session import check_database_connection
from app.infrastructure.storage.minio_client import check_minio_connection
from app.schemas.health import DependencyStatus, HealthResponse, LivenessResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=LivenessResponse, summary="Liveness probe")
async def liveness() -> LivenessResponse:
    """Return a simple liveness signal.

    Returns:
        A `LivenessResponse` indicating the process is running. This never
        checks downstream dependencies, so it stays fast and reliable for
        Kubernetes liveness probes.
    """
    return LivenessResponse()


@router.get("/ready", response_model=HealthResponse, summary="Readiness probe")
async def readiness() -> HealthResponse:
    """Check the application and all downstream dependencies.

    Returns:
        A `HealthResponse` with overall status `"ok"` if every dependency is
        healthy, or `"degraded"` if any dependency check fails.
    """
    settings = get_settings()

    dependencies = [
        DependencyStatus(name="postgres", healthy=await check_database_connection()),
        DependencyStatus(name="redis", healthy=await check_redis_connection()),
        DependencyStatus(name="minio", healthy=check_minio_connection()),
    ]

    overall_status = "ok" if all(dep.healthy for dep in dependencies) else "degraded"

    return HealthResponse(
        status=overall_status,
        version=__version__,
        environment=settings.environment,
        dependencies=dependencies,
    )
