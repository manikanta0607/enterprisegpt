"""Framework-agnostic domain entities.

These dataclasses represent core business concepts independent of how they
are persisted (SQLAlchemy) or transported (Pydantic/HTTP). Services operate
on these entities; repositories translate to/from ORM models at the boundary.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.enums import DocumentStatus, Role


@dataclass(frozen=True, slots=True)
class Organization:
    """A tenant organization within the platform."""

    id: UUID
    name: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class User:
    """A platform user, always scoped to exactly one organization."""

    id: UUID
    email: str
    full_name: str
    role: Role
    organization_id: UUID
    is_active: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Document:
    """An uploaded source document within an organization's knowledge base."""

    id: UUID
    organization_id: UUID
    uploaded_by_user_id: UUID
    filename: str
    content_type: str
    storage_key: str
    status: DocumentStatus
    error_message: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Chunk:
    """A single chunk of extracted text from a parsed document."""

    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    token_count: int
    created_at: datetime
