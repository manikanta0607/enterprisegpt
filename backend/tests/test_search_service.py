"""Tests for SearchService, mocking repositories and the embedding service
so these run without a live Postgres/pgvector or Google API access."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.entities import Chunk, Document
from app.domain.enums import DocumentStatus
from app.services.query_rewrite import NoOpQueryRewriter
from app.services.search.search_service import SearchService

pytestmark = pytest.mark.asyncio


def _make_chunk(chunk_id: uuid.UUID, document_id: uuid.UUID, content: str) -> Chunk:
    return Chunk(
        id=chunk_id,
        document_id=document_id,
        chunk_index=0,
        content=content,
        token_count=len(content.split()),
        created_at=datetime.now(timezone.utc),
    )


def _make_document(document_id: uuid.UUID, filename: str) -> Document:
    return Document(
        id=document_id,
        organization_id=uuid.uuid4(),
        uploaded_by_user_id=uuid.uuid4(),
        filename=filename,
        content_type="application/pdf",
        storage_key="key",
        status=DocumentStatus.COMPLETED,
        error_message=None,
        created_at=datetime.now(timezone.utc),
    )


async def test_search_returns_empty_when_organization_has_no_chunks():
    """search() should return an empty list rather than error on an empty corpus."""
    chunk_repo = AsyncMock()
    chunk_repo.list_content_by_organization.return_value = []

    service = SearchService(
        chunk_repository=chunk_repo,
        document_repository=AsyncMock(),
        embedding_service=MagicMock(),
        query_rewriter=NoOpQueryRewriter(),
    )

    results = await service.search(organization_id=uuid.uuid4(), query="anything", top_k=5)

    assert results == []


async def test_search_combines_vector_and_bm25_and_returns_compressed_results():
    """search() should fuse vector + BM25 rankings and return compressed content
    with the correct filename attached."""
    org_id = uuid.uuid4()
    document_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    other_chunk_id = uuid.uuid4()

    chunk = _make_chunk(chunk_id, document_id, "Quarterly revenue grew significantly this year.")
    other_chunk = _make_chunk(other_chunk_id, document_id, "The office plants need watering.")
    document = _make_document(document_id, "q3_report.pdf")

    chunk_repo = AsyncMock()
    chunk_repo.list_content_by_organization.return_value = [
        (chunk_id, chunk.content),
        (other_chunk_id, other_chunk.content),
    ]
    chunk_repo.search_by_vector.return_value = [(chunk_id, 0.9)]
    chunk_repo.get_by_ids.return_value = [chunk]

    document_repo = AsyncMock()
    document_repo.get_by_id.return_value = document

    embedding_service = MagicMock()
    embedding_service.embed_text.return_value = [0.1, 0.2, 0.3]

    service = SearchService(
        chunk_repository=chunk_repo,
        document_repository=document_repo,
        embedding_service=embedding_service,
        query_rewriter=NoOpQueryRewriter(),
    )

    results = await service.search(organization_id=org_id, query="quarterly revenue", top_k=5)

    assert len(results) == 1
    assert results[0].chunk_id == chunk_id
    assert results[0].filename == "q3_report.pdf"
    assert "revenue" in results[0].content.lower()


async def test_search_falls_back_gracefully_when_vector_search_fails():
    """If embedding/vector search raises, search() should still return BM25-only results."""
    org_id = uuid.uuid4()
    document_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    other_chunk_id = uuid.uuid4()
    third_chunk_id = uuid.uuid4()
    chunk = _make_chunk(chunk_id, document_id, "Machine learning models require training data.")
    other_chunk = _make_chunk(other_chunk_id, document_id, "The quarterly budget meeting is on Friday.")
    third_chunk = _make_chunk(third_chunk_id, document_id, "Office renovations begin next month.")
    document = _make_document(document_id, "ml_notes.pdf")

    chunk_repo = AsyncMock()
    chunk_repo.list_content_by_organization.return_value = [
        (chunk_id, chunk.content),
        (other_chunk_id, other_chunk.content),
        (third_chunk_id, third_chunk.content),
    ]
    chunk_repo.get_by_ids.return_value = [chunk]

    document_repo = AsyncMock()
    document_repo.get_by_id.return_value = document

    embedding_service = MagicMock()
    embedding_service.embed_text.side_effect = RuntimeError("embedding API unavailable")

    service = SearchService(
        chunk_repository=chunk_repo,
        document_repository=document_repo,
        embedding_service=embedding_service,
        query_rewriter=NoOpQueryRewriter(),
    )

    results = await service.search(organization_id=org_id, query="machine learning", top_k=5)

    assert len(results) == 1
    assert results[0].chunk_id == chunk_id
    chunk_repo.search_by_vector.assert_not_called()
