"""Repository for user persistence.

The repository pattern isolates SQLAlchemy query logic from the service
layer, and translates between ORM models (`UserModel`) and domain entities
(`User`) at the boundary — the service layer never sees a `UserModel`.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import User
from app.domain.enums import Role
from app.infrastructure.database.models import UserModel


def _to_entity(model: UserModel) -> User:
    """Convert a `UserModel` ORM row into a `User` domain entity.

    Args:
        model: The ORM model instance.

    Returns:
        The corresponding framework-agnostic `User` entity.
    """
    return User(
        id=model.id,
        email=model.email,
        full_name=model.full_name,
        role=Role(model.role),
        organization_id=model.organization_id,
        is_active=model.is_active,
        created_at=model.created_at,
    )


class UserRepository:
    """Data access layer for the `users` table."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a request-scoped session.

        Args:
            session: The active `AsyncSession` for this request.
        """
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Fetch a user by primary key.

        Args:
            user_id: The user's UUID.

        Returns:
            The matching `User` entity, or None if not found.
        """
        model = await self._session.get(UserModel, user_id)
        return _to_entity(model) if model else None

    async def get_by_google_sub(self, google_sub: str) -> User | None:
        """Fetch a user by their Google account subject identifier.

        Args:
            google_sub: The `sub` claim from a verified Google ID token.

        Returns:
            The matching `User` entity, or None if not found.
        """
        result = await self._session.execute(
            select(UserModel).where(UserModel.google_sub == google_sub)
        )
        model = result.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def get_by_email(self, email: str) -> User | None:
        """Fetch a user by email address.

        Args:
            email: The user's email address.

        Returns:
            The matching `User` entity, or None if not found.
        """
        result = await self._session.execute(select(UserModel).where(UserModel.email == email))
        model = result.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def create(
        self,
        *,
        email: str,
        full_name: str,
        google_sub: str,
        organization_id: uuid.UUID,
        role: Role = Role.MEMBER,
    ) -> User:
        """Create a new user record.

        Args:
            email: The user's email address.
            full_name: The user's display name.
            google_sub: The Google account subject identifier.
            organization_id: The organization this user belongs to.
            role: The role to assign; defaults to MEMBER.

        Returns:
            The newly created `User` entity.
        """
        model = UserModel(
            email=email,
            full_name=full_name,
            google_sub=google_sub,
            organization_id=organization_id,
            role=role.value,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_entity(model)

    async def list_by_organization(self, organization_id: uuid.UUID) -> list[User]:
        """List all users belonging to an organization.

        Args:
            organization_id: The organization's UUID.

        Returns:
            A list of `User` entities, ordered by creation date.
        """
        result = await self._session.execute(
            select(UserModel)
            .where(UserModel.organization_id == organization_id)
            .order_by(UserModel.created_at)
        )
        return [_to_entity(model) for model in result.scalars().all()]
