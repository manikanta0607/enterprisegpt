"""Pydantic request/response models for document endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.enums import DocumentStatus


class DocumentResponse(BaseModel):
    """Public representation of an uploaded document."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    uploaded_by_user_id: uuid.UUID
    filename: str
    content_type: str
    status: DocumentStatus
    error_message: str | None
    created_at: datetime


class ChunkResponse(BaseModel):
    """Public representation of a single document chunk."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content: str
    token_count: int
    created_at: datetime
