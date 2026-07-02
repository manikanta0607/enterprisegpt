"""Repository for chunk persistence."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Chunk
from app.infrastructure.database.models import ChunkModel


def _to_entity(model: ChunkModel) -> Chunk:
    """Convert a `ChunkModel` ORM row into a `Chunk` domain entity.

    Args:
        model: The ORM model instance.

    Returns:
        The corresponding `Chunk` domain entity.
    """
    return Chunk(
        id=model.id,
        document_id=model.document_id,
        chunk_index=model.chunk_index,
        content=model.content,
        token_count=model.token_count,
        created_at=model.created_at,
    )


class ChunkRepository:
    """Data access layer for the `chunks` table."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a request-scoped session.

        Args:
            session: The active `AsyncSession` for this request.
        """
        self._session = session

    async def bulk_create(
        self, document_id: uuid.UUID, chunks: list[tuple[int, str, int]]
    ) -> list[Chunk]:
        """Persist multiple chunks for a document in one transaction.

        Args:
            document_id: The parent document's UUID.
            chunks: A list of (chunk_index, content, token_count) tuples.

        Returns:
            The newly created `Chunk` entities.
        """
        models = [
            ChunkModel(
                document_id=document_id,
                chunk_index=index,
                content=content,
                token_count=token_count,
            )
            for index, content, token_count in chunks
        ]
        self._session.add_all(models)
        await self._session.flush()
        for model in models:
            await self._session.refresh(model)
        await self._session.commit()
        return [_to_entity(model) for model in models]

    async def list_by_document(self, document_id: uuid.UUID) -> list[Chunk]:
        """List all chunks for a document, in order.

        Args:
            document_id: The parent document's UUID.

        Returns:
            A list of `Chunk` entities ordered by `chunk_index`.
        """
        result = await self._session.execute(
            select(ChunkModel)
            .where(ChunkModel.document_id == document_id)
            .order_by(ChunkModel.chunk_index)
        )
        return [_to_entity(model) for model in result.scalars().all()]
