"""Repository for organization persistence."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Organization
from app.infrastructure.database.models import OrganizationModel


def _to_entity(model: OrganizationModel) -> Organization:
    """Convert an `OrganizationModel` ORM row into an `Organization` entity.

    Args:
        model: The ORM model instance.

    Returns:
        The corresponding `Organization` domain entity.
    """
    return Organization(id=model.id, name=model.name, created_at=model.created_at)


class OrganizationRepository:
    """Data access layer for the `organizations` table."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a request-scoped session.

        Args:
            session: The active `AsyncSession` for this request.
        """
        self._session = session

    async def get_by_id(self, organization_id: uuid.UUID) -> Organization | None:
        """Fetch an organization by primary key.

        Args:
            organization_id: The organization's UUID.

        Returns:
            The matching `Organization` entity, or None if not found.
        """
        model = await self._session.get(OrganizationModel, organization_id)
        return _to_entity(model) if model else None

    async def create(self, *, name: str) -> Organization:
        """Create a new organization.

        Args:
            name: The organization's display name.

        Returns:
            The newly created `Organization` entity.
        """
        model = OrganizationModel(name=name)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_entity(model)
