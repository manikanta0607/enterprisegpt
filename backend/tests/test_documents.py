"""Tests for /documents endpoints.

Mocks the MinIO storage layer and repositories so these run without a live
Postgres or MinIO instance, following the same dependency-override pattern
established in test_users.py.
"""

import io
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.api.deps import get_current_user, get_document_repository
from app.domain.entities import Document, User
from app.domain.enums import DocumentStatus, Role

pytestmark = pytest.mark.asyncio


def _make_user(role: Role = Role.MEMBER) -> User:
    return User(
        id=uuid.uuid4(),
        email="uploader@example.com",
        full_name="Uploader",
        role=role,
        organization_id=uuid.uuid4(),
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


def _make_document(user: User, status: DocumentStatus = DocumentStatus.PENDING) -> Document:
    return Document(
        id=uuid.uuid4(),
        organization_id=user.organization_id,
        uploaded_by_user_id=user.id,
        filename="report.pdf",
        content_type="application/pdf",
        storage_key=f"{user.organization_id}/some-key_report.pdf",
        status=status,
        error_message=None,
        created_at=datetime.now(timezone.utc),
    )


async def test_upload_document_returns_pending_status(app, client):
    """POST /documents should store the file and return status 'pending'."""
    user = _make_user(Role.MEMBER)
    document = _make_document(user)

    fake_repo = AsyncMock()
    fake_repo.create.return_value = document

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_document_repository] = lambda: fake_repo

    with patch("app.services.document_service.upload_document_bytes") as mock_upload, patch(
        "app.api.v1.endpoints.documents.process_document", new=AsyncMock()
    ):
        response = await client.post(
            "/api/v1/documents",
            files={"file": ("report.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
        )

    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    assert response.json()["filename"] == "report.pdf"
    mock_upload.assert_called_once()

    app.dependency_overrides.clear()


async def test_upload_rejects_unsupported_content_type(app, client):
    """POST /documents should reject a content type with no registered parser."""
    user = _make_user(Role.MEMBER)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_document_repository] = lambda: AsyncMock()

    response = await client.post(
        "/api/v1/documents",
        files={"file": ("archive.zip", io.BytesIO(b"PK\x03\x04"), "application/zip")},
    )

    assert response.status_code == 422

    app.dependency_overrides.clear()


async def test_upload_forbidden_for_viewer(app, client):
    """POST /documents should return 403 for a VIEWER (below MEMBER minimum)."""
    user = _make_user(Role.VIEWER)
    app.dependency_overrides[get_current_user] = lambda: user

    response = await client.post(
        "/api/v1/documents",
        files={"file": ("report.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
    )

    assert response.status_code == 403

    app.dependency_overrides.clear()


async def test_get_document_not_found_for_other_organization(app, client):
    """GET /documents/{id} should 404 when the document belongs to another org."""
    user = _make_user(Role.MEMBER)
    other_org_document = _make_document(_make_user(Role.MEMBER))  # different org

    fake_repo = AsyncMock()
    fake_repo.get_by_id.return_value = other_org_document

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_document_repository] = lambda: fake_repo

    response = await client.get(f"/api/v1/documents/{other_org_document.id}")

    assert response.status_code == 404

    app.dependency_overrides.clear()


async def test_list_documents_returns_organization_scoped_results(app, client):
    """GET /documents should return only the caller's organization's documents."""
    user = _make_user(Role.VIEWER)
    document = _make_document(user, status=DocumentStatus.COMPLETED)

    fake_repo = AsyncMock()
    fake_repo.list_by_organization.return_value = [document]

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_document_repository] = lambda: fake_repo

    response = await client.get("/api/v1/documents")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "completed"

    app.dependency_overrides.clear()
