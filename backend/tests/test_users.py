"""Tests for /users endpoints using FastAPI dependency overrides.

These tests exercise the real endpoint + RBAC wiring without needing a live
Postgres instance: `get_current_user` and `get_user_repository` are swapped
for fakes, the same technique used for integration testing with a real DB
in later phases once Postgres is available in CI.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.api.deps import get_current_user, get_user_repository
from app.domain.entities import User
from app.domain.enums import Role

pytestmark = pytest.mark.asyncio


def _make_user(role: Role) -> User:
    return User(
        id=uuid.uuid4(),
        email="user@example.com",
        full_name="Test User",
        role=role,
        organization_id=uuid.uuid4(),
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


async def test_get_me_returns_current_user(app, client):
    """GET /users/me should return the authenticated user's own profile."""
    fake_user = _make_user(Role.MEMBER)
    app.dependency_overrides[get_current_user] = lambda: fake_user

    response = await client.get("/api/v1/users/me")

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"
    assert response.json()["role"] == "member"

    app.dependency_overrides.clear()


async def test_list_users_forbidden_for_non_admin(app, client):
    """GET /users should return 403 for a MEMBER (below the ADMIN minimum)."""
    fake_user = _make_user(Role.MEMBER)
    app.dependency_overrides[get_current_user] = lambda: fake_user

    response = await client.get("/api/v1/users")

    assert response.status_code == 403
    assert response.json()["error"] == "InsufficientRoleError"

    app.dependency_overrides.clear()


async def test_list_users_allowed_for_admin(app, client):
    """GET /users should succeed for an ADMIN and return the repository's list."""
    fake_admin = _make_user(Role.ADMIN)
    fake_repo = AsyncMock()
    fake_repo.list_by_organization.return_value = [fake_admin]

    app.dependency_overrides[get_current_user] = lambda: fake_admin
    app.dependency_overrides[get_user_repository] = lambda: fake_repo

    response = await client.get("/api/v1/users")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["email"] == "user@example.com"

    app.dependency_overrides.clear()


async def test_me_requires_authentication(client):
    """GET /users/me without a Bearer token should be rejected."""
    response = await client.get("/api/v1/users/me")

    assert response.status_code in (401, 403)
