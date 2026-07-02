"""Pydantic response models for health check endpoints."""

from pydantic import BaseModel, Field


class DependencyStatus(BaseModel):
    """Health status of a single downstream dependency."""

    name: str = Field(..., description="Dependency name, e.g. 'postgres'")
    healthy: bool = Field(..., description="Whether the dependency is reachable")


class HealthResponse(BaseModel):
    """Overall health check response."""

    status: str = Field(..., description="'ok' if all dependencies are healthy, else 'degraded'")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Deployment environment")
    dependencies: list[DependencyStatus] = Field(
        default_factory=list, description="Per-dependency health status"
    )


class LivenessResponse(BaseModel):
    """Lightweight liveness probe response (no dependency checks)."""

    status: str = Field(default="alive", description="Always 'alive' if the process can respond")
