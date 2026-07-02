"""Framework-agnostic domain entities.

These dataclasses represent core business concepts independent of how they
are persisted (SQLAlchemy) or transported (Pydantic/HTTP). Services operate
on these entities; repositories translate to/from ORM models at the boundary.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.enums import Role


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
