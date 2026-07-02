"""Shared pytest fixtures for the backend test suite."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
def app():
    """Provide a fresh FastAPI app instance for testing.

    Returns:
        The configured FastAPI application.
    """
    return create_app()


@pytest.fixture
async def client(app):
    """Provide an async HTTP client wired directly to the ASGI app.

    Using `ASGITransport` avoids the need for a running server process,
    making tests fast and hermetic.

    Args:
        app: The FastAPI app fixture.

    Yields:
        An `AsyncClient` for making requests against the app.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
