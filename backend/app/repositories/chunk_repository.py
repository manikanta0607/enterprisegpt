"""Repository for chunk persistence."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Chunk
from app.infrastructure.database.models import ChunkModel, DocumentModel


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
        embedding=list(model.embedding) if model.embedding is not None else None,
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

    async def update_embedding(self, chunk_id: uuid.UUID, embedding: list[float]) -> None:
        """Store a computed embedding vector for a chunk.

        Args:
            chunk_id: The chunk's UUID.
            embedding: The embedding vector, matching the configured dimensionality.
        """
        model = await self._session.get(ChunkModel, chunk_id)
        if model is not None:
            model.embedding = embedding
            await self._session.commit()

    async def list_content_by_organization(
        self, organization_id: uuid.UUID
    ) -> list[tuple[uuid.UUID, str]]:
        """Fetch (chunk_id, content) pairs for every chunk in an organization.

        Used as the corpus for BM25 keyword search, which — unlike vector
        similarity — has no native pgvector-style index here and is scored
        in-process. Fine for the corpus sizes this phase targets; a
        dedicated search engine (OpenSearch/Elasticsearch) is the natural
        upgrade path if an organization's corpus grows very large.

        Args:
            organization_id: The organization to scope the corpus to.

        Returns:
            A list of (chunk_id, content) tuples.
        """
        result = await self._session.execute(
            select(ChunkModel.id, ChunkModel.content)
            .join(DocumentModel, DocumentModel.id == ChunkModel.document_id)
            .where(DocumentModel.organization_id == organization_id)
        )
        return [(row.id, row.content) for row in result.all()]

    async def search_by_vector(
        self, organization_id: uuid.UUID, query_embedding: list[float], top_k: int = 20
    ) -> list[tuple[uuid.UUID, float]]:
        """Rank chunks by cosine similarity to a query embedding, using pgvector.

        Args:
            organization_id: The organization to scope the search to.
            query_embedding: The embedding vector of the search query.
            top_k: Maximum number of results to return.

        Returns:
            A list of (chunk_id, similarity_score) tuples, most similar
            first. `similarity_score` is `1 - cosine_distance`, so higher is
            better (range roughly -1 to 1).
        """
        distance = ChunkModel.embedding.cosine_distance(query_embedding)
        result = await self._session.execute(
            select(ChunkModel.id, distance.label("distance"))
            .join(DocumentModel, DocumentModel.id == ChunkModel.document_id)
            .where(
                DocumentModel.organization_id == organization_id,
                ChunkModel.embedding.is_not(None),
            )
            .order_by(distance)
            .limit(top_k)
        )
        return [(row.id, 1 - row.distance) for row in result.all()]

    async def get_by_ids(self, chunk_ids: list[uuid.UUID]) -> list[Chunk]:
        """Fetch multiple chunks by their IDs, in arbitrary order.

        Args:
            chunk_ids: The chunk UUIDs to fetch.

        Returns:
            The matching `Chunk` entities. Callers that need a specific
            order (e.g. a ranked search result) should reorder the returned
            list themselves.
        """
        if not chunk_ids:
            return []
        result = await self._session.execute(
            select(ChunkModel).where(ChunkModel.id.in_(chunk_ids))
        )
        return [_to_entity(model) for model in result.scalars().all()]
