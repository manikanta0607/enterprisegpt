"""Pydantic request/response models for conversation endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import MessageRole


class ConversationResponse(BaseModel):
    """Public representation of a conversation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    title: str
    summary: str | None
    created_at: datetime


class CitationResponse(BaseModel):
    """Public representation of a source citation."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    excerpt: str


class MessageResponse(BaseModel):
    """Public representation of a single conversation message."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: MessageRole
    content: str
    citations: list[CitationResponse]
    created_at: datetime


class SendMessageRequest(BaseModel):
    """Request body for posting a new user message."""

    content: str = Field(..., min_length=1, max_length=4000, description="The user's message")
