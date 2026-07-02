"""Repository for document persistence."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Document
from app.domain.enums import DocumentStatus
from app.infrastructure.database.models import DocumentModel


def _to_entity(model: DocumentModel) -> Document:
    """Convert a `DocumentModel` ORM row into a `Document` domain entity.

    Args:
        model: The ORM model instance.

    Returns:
        The corresponding `Document` domain entity.
    """
    return Document(
        id=model.id,
        organization_id=model.organization_id,
        uploaded_by_user_id=model.uploaded_by_user_id,
        filename=model.filename,
        content_type=model.content_type,
        storage_key=model.storage_key,
        status=DocumentStatus(model.status),
        error_message=model.error_message,
        created_at=model.created_at,
    )


class DocumentRepository:
    """Data access layer for the `documents` table."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a request-scoped session.

        Args:
            session: The active `AsyncSession` for this request.
        """
        self._session = session

    async def create(
        self,
        *,
        organization_id: uuid.UUID,
        uploaded_by_user_id: uuid.UUID,
        filename: str,
        content_type: str,
        storage_key: str,
    ) -> Document:
        """Create a new document record in PENDING status.

        Args:
            organization_id: The organization that owns this document.
            uploaded_by_user_id: The user who uploaded the file.
            filename: The original filename.
            content_type: The MIME type of the uploaded file.
            storage_key: The MinIO object key where the raw file is stored.

        Returns:
            The newly created `Document` entity.
        """
        model = DocumentModel(
            organization_id=organization_id,
            uploaded_by_user_id=uploaded_by_user_id,
            filename=filename,
            content_type=content_type,
            storage_key=storage_key,
            status=DocumentStatus.PENDING.value,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_entity(model)

    async def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        """Fetch a document by primary key.

        Args:
            document_id: The document's UUID.

        Returns:
            The matching `Document` entity, or None if not found.
        """
        model = await self._session.get(DocumentModel, document_id)
        return _to_entity(model) if model else None

    async def list_by_organization(self, organization_id: uuid.UUID) -> list[Document]:
        """List all documents belonging to an organization, newest first.

        Args:
            organization_id: The organization's UUID.

        Returns:
            A list of `Document` entities.
        """
        result = await self._session.execute(
            select(DocumentModel)
            .where(DocumentModel.organization_id == organization_id)
            .order_by(DocumentModel.created_at.desc())
        )
        return [_to_entity(model) for model in result.scalars().all()]

    async def update_status(
        self, document_id: uuid.UUID, status: DocumentStatus, error_message: str | None = None
    ) -> None:
        """Update a document's ingestion status.

        Args:
            document_id: The document's UUID.
            status: The new status to set.
            error_message: Error details if `status` is FAILED, else None.
        """
        model = await self._session.get(DocumentModel, document_id)
        if model is not None:
            model.status = status.value
            model.error_message = error_message
            await self._session.commit()
