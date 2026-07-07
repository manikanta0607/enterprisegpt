"""Repository for conversation persistence."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Conversation
from app.infrastructure.database.models import ConversationModel


def _to_entity(model: ConversationModel) -> Conversation:
    """Convert a `ConversationModel` ORM row into a `Conversation` entity.

    Args:
        model: The ORM model instance.

    Returns:
        The corresponding `Conversation` domain entity.
    """
    return Conversation(
        id=model.id,
        organization_id=model.organization_id,
        user_id=model.user_id,
        title=model.title,
        summary=model.summary,
        created_at=model.created_at,
    )


class ConversationRepository:
    """Data access layer for the `conversations` table."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a request-scoped session.

        Args:
            session: The active `AsyncSession` for this request.
        """
        self._session = session

    async def create(
        self, *, organization_id: uuid.UUID, user_id: uuid.UUID, title: str = "New conversation"
    ) -> Conversation:
        """Create a new conversation.

        Args:
            organization_id: The owning organization.
            user_id: The user who started the conversation.
            title: A display title, initially generic and updatable later.

        Returns:
            The newly created `Conversation` entity.
        """
        model = ConversationModel(organization_id=organization_id, user_id=user_id, title=title)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_entity(model)

    async def get_by_id(self, conversation_id: uuid.UUID) -> Conversation | None:
        """Fetch a conversation by primary key.

        Args:
            conversation_id: The conversation's UUID.

        Returns:
            The matching `Conversation` entity, or None if not found.
        """
        model = await self._session.get(ConversationModel, conversation_id)
        return _to_entity(model) if model else None

    async def list_by_user(self, user_id: uuid.UUID) -> list[Conversation]:
        """List all conversations started by a user, newest first.

        Args:
            user_id: The user's UUID.

        Returns:
            A list of `Conversation` entities.
        """
        result = await self._session.execute(
            select(ConversationModel)
            .where(ConversationModel.user_id == user_id)
            .order_by(ConversationModel.created_at.desc())
        )
        return [_to_entity(model) for model in result.scalars().all()]

    async def update_summary(self, conversation_id: uuid.UUID, summary: str) -> None:
        """Persist a compressed long-term memory summary for a conversation.

        Args:
            conversation_id: The conversation's UUID.
            summary: The new summary text, replacing any previous summary.
        """
        model = await self._session.get(ConversationModel, conversation_id)
        if model is not None:
            model.summary = summary
            await self._session.commit()
