"""Search service: orchestrates the full hybrid retrieval pipeline.

Pipeline: rewrite query -> embed query -> vector search + BM25 search in
parallel -> Reciprocal Rank Fusion -> term-overlap re-rank -> extractive
context compression -> return ranked, compressed results.
"""

import asyncio
import uuid
from dataclasses import dataclass

from app.core.logging import get_logger
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.services.context_compression import compress_text
from app.services.embeddings import EmbeddingService
from app.services.query_rewrite import QueryRewriter
from app.services.search.bm25 import bm25_rank
from app.services.search.fusion import reciprocal_rank_fusion
from app.services.search.reranker import rerank_by_term_overlap

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SearchResult:
    """A single ranked, compressed search result."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    content: str
    score: float


class SearchService:
    """Coordinates hybrid search across vector similarity and BM25."""

    def __init__(
        self,
        chunk_repository: ChunkRepository,
        document_repository: DocumentRepository,
        embedding_service: EmbeddingService,
        query_rewriter: QueryRewriter,
    ) -> None:
        """Initialize the search service with its collaborators.

        Args:
            chunk_repository: Repository for chunk retrieval and vector search.
            document_repository: Repository for looking up document filenames.
            embedding_service: Service used to embed the (possibly rewritten) query.
            query_rewriter: Strategy used to expand/clarify the raw query.
        """
        self._chunks = chunk_repository
        self._documents = document_repository
        self._embeddings = embedding_service
        self._query_rewriter = query_rewriter

    async def search(
        self, *, organization_id: uuid.UUID, query: str, top_k: int = 10
    ) -> list[SearchResult]:
        """Run the full hybrid search pipeline for a query.

        Args:
            organization_id: The organization to scope the search to.
            query: The raw user search query.
            top_k: Maximum number of results to return.

        Returns:
            A list of `SearchResult`, best match first. Returns an empty
            list if the organization has no chunks yet.
        """
        rewritten_query = self._query_rewriter.rewrite(query)

        corpus = await self._chunks.list_content_by_organization(organization_id)
        if not corpus:
            return []

        bm25_ids = [chunk_id for chunk_id, _ in bm25_rank(rewritten_query, corpus, top_k=top_k * 2)]

        vector_ids: list[uuid.UUID] = []
        try:
            query_embedding = self._embeddings.embed_text(
                rewritten_query, task_type="retrieval_query"
            )
            vector_ids = [
                chunk_id
                for chunk_id, _ in await self._chunks.search_by_vector(
                    organization_id, query_embedding, top_k=top_k * 2
                )
            ]
        except Exception:
            logger.warning("Vector search unavailable; falling back to BM25-only results")

        fused = reciprocal_rank_fusion([vector_ids, bm25_ids], top_k=top_k * 2)
        if not fused:
            return []

        contents_by_id = dict(corpus)
        reranked = rerank_by_term_overlap(rewritten_query, fused, contents_by_id)[:top_k]

        return await self._build_results(reranked, rewritten_query, contents_by_id)

    async def _build_results(
        self,
        ranked: list[tuple[uuid.UUID, float]],
        query: str,
        contents_by_id: dict[uuid.UUID, str],
    ) -> list[SearchResult]:
        """Assemble final `SearchResult` objects with filenames and compressed content.

        Args:
            ranked: (chunk_id, score) pairs in final rank order.
            query: The query used to drive context compression.
            contents_by_id: Full chunk content keyed by chunk_id.

        Returns:
            The assembled, ordered `SearchResult` list.
        """
        chunks = await self._chunks.get_by_ids([chunk_id for chunk_id, _ in ranked])
        chunks_by_id = {chunk.id: chunk for chunk in chunks}

        document_ids = {chunk.document_id for chunk in chunks}
        documents = await asyncio.gather(
            *(self._documents.get_by_id(doc_id) for doc_id in document_ids)
        )
        filenames_by_document_id = {doc.id: doc.filename for doc in documents if doc is not None}

        results = []
        for chunk_id, score in ranked:
            chunk = chunks_by_id.get(chunk_id)
            if chunk is None:
                continue
            results.append(
                SearchResult(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    filename=filenames_by_document_id.get(chunk.document_id, "unknown"),
                    content=compress_text(query, contents_by_id.get(chunk_id, chunk.content)),
                    score=score,
                )
            )
        return results
