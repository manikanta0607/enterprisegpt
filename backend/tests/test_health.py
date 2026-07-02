"""Tests for the health check endpoints."""

import pytest

pytestmark = pytest.mark.asyncio


async def test_liveness_returns_alive(client):
    """The liveness probe should always return 200 and status 'alive'."""
    response = await client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


async def test_readiness_returns_dependency_statuses(client):
    """The readiness probe should report status for postgres, redis, and minio.

    This test does not assert dependencies are healthy (they may not be
    running in a pure unit-test environment) — it asserts the contract
    shape is correct, which is what matters for Phase 1.
    """
    response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    body = response.json()

    assert body["status"] in {"ok", "degraded"}
    assert "version" in body
    assert "environment" in body

    dependency_names = {dep["name"] for dep in body["dependencies"]}
    assert dependency_names == {"postgres", "redis", "minio"}


async def test_openapi_docs_available(client):
    """The OpenAPI schema should be served for API documentation."""
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "EnterpriseGPT"
