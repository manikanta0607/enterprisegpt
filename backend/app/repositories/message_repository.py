"""Repository for message persistence."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Citation, Message
from app.domain.enums import MessageRole
from app.infrastructure.database.models import MessageModel


def _to_entity(model: MessageModel) -> Message:
    """Convert a `MessageModel` ORM row into a `Message` domain entity.

    Args:
        model: The ORM model instance.

    Returns:
        The corresponding `Message` domain entity.
    """
    return Message(
        id=model.id,
        conversation_id=model.conversation_id,
        role=MessageRole(model.role),
        content=model.content,
        citations=[
            Citation(
                chunk_id=uuid.UUID(c["chunk_id"]),
                document_id=uuid.UUID(c["document_id"]),
                filename=c["filename"],
                excerpt=c["excerpt"],
            )
            for c in model.citations
        ],
        created_at=model.created_at,
    )


class MessageRepository:
    """Data access layer for the `messages` table."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a request-scoped session.

        Args:
            session: The active `AsyncSession` for this request.
        """
        self._session = session

    async def create(
        self,
        *,
        conversation_id: uuid.UUID,
        role: MessageRole,
        content: str,
        citations: list[Citation] | None = None,
    ) -> Message:
        """Create a new message in a conversation.

        Args:
            conversation_id: The parent conversation's UUID.
            role: Whether this message is from the user or the assistant.
            content: The message text.
            citations: Source references for assistant messages, if any.

        Returns:
            The newly created `Message` entity.
        """
        model = MessageModel(
            conversation_id=conversation_id,
            role=role.value,
            content=content,
            citations=[
                {
                    "chunk_id": str(c.chunk_id),
                    "document_id": str(c.document_id),
                    "filename": c.filename,
                    "excerpt": c.excerpt,
                }
                for c in (citations or [])
            ],
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        await self._session.commit()
        return _to_entity(model)

    async def list_by_conversation(
        self, conversation_id: uuid.UUID, limit: int | None = None
    ) -> list[Message]:
        """List messages in a conversation, oldest first.

        Args:
            conversation_id: The parent conversation's UUID.
            limit: If given, only the most recent `limit` messages are
                returned (still ordered oldest-first).

        Returns:
            A list of `Message` entities.
        """
        query = (
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at.desc())
        )
        if limit is not None:
            query = query.limit(limit)

        result = await self._session.execute(query)
        messages = [_to_entity(model) for model in result.scalars().all()]
        return list(reversed(messages))

    async def count_by_conversation(self, conversation_id: uuid.UUID) -> int:
        """Count the total number of messages in a conversation.

        Args:
            conversation_id: The parent conversation's UUID.

        Returns:
            The message count.
        """
        result = await self._session.execute(
            select(func.count(MessageModel.id)).where(
                MessageModel.conversation_id == conversation_id
            )
        )
        return result.scalar_one()
