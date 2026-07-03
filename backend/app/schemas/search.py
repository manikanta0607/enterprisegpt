"""Pydantic request/response models for the search endpoint."""

import uuid

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Request body for a hybrid search query."""

    query: str = Field(..., min_length=1, max_length=1000, description="The search query")
    top_k: int = Field(default=10, ge=1, le=50, description="Maximum number of results")


class SearchResultItem(BaseModel):
    """A single ranked, compressed search result."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    content: str = Field(..., description="Compressed, most-relevant excerpt of the chunk")
    score: float = Field(..., description="Final re-ranked relevance score")


class SearchResponse(BaseModel):
    """Response body for a hybrid search query."""

    query: str = Field(..., description="The (possibly rewritten) query actually searched")
    results: list[SearchResultItem]
