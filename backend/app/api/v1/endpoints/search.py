"""Hybrid search endpoint."""

from fastapi import APIRouter, Depends

from app.api.deps import (
    get_chunk_repository,
    get_current_user,
    get_document_repository,
)
from app.domain.entities import User
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.schemas.search import SearchRequest, SearchResponse, SearchResultItem
from app.services.embeddings import EmbeddingService
from app.services.query_rewrite import get_query_rewriter
from app.services.search.search_service import SearchService

router = APIRouter(prefix="/search", tags=["search"])


def _get_search_service(
    chunk_repository: ChunkRepository = Depends(get_chunk_repository),
    document_repository: DocumentRepository = Depends(get_document_repository),
) -> SearchService:
    """Provide a `SearchService` with its collaborators wired up.

    Args:
        chunk_repository: Injected chunk repository.
        document_repository: Injected document repository.

    Returns:
        A configured `SearchService` instance.
    """
    return SearchService(
        chunk_repository=chunk_repository,
        document_repository=document_repository,
        embedding_service=EmbeddingService(),
        query_rewriter=get_query_rewriter(),
    )


@router.post("", response_model=SearchResponse, summary="Hybrid search over your documents")
async def search(
    body: SearchRequest,
    current_user: User = Depends(get_current_user),
    search_service: SearchService = Depends(_get_search_service),
) -> SearchResponse:
    """Run hybrid (vector + BM25) search over the caller's organization's documents.

    Combines semantic vector similarity with BM25 keyword matching via
    Reciprocal Rank Fusion, re-ranks by literal term overlap, and returns
    compressed, most-relevant excerpts from each matching chunk.
    """
    results = await search_service.search(
        organization_id=current_user.organization_id, query=body.query, top_k=body.top_k
    )

    return SearchResponse(
        query=body.query,
        results=[SearchResultItem(**result.__dict__) for result in results],
    )
