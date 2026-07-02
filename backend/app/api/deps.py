"""Shared FastAPI dependencies: current user resolution, repositories.

Centralizing these here keeps endpoint modules thin and ensures every
protected route resolves the current user identically.
"""

import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import TokenType, decode_token
from app.domain.entities import User
from app.infrastructure.database.session import get_db_session
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.user_repository import UserRepository

_bearer_scheme = HTTPBearer(auto_error=True)


async def get_user_repository(
    session: AsyncSession = Depends(get_db_session),
) -> UserRepository:
    """Provide a `UserRepository` bound to the request's DB session.

    Args:
        session: The request-scoped database session.

    Returns:
        A `UserRepository` instance.
    """
    return UserRepository(session)


async def get_document_repository(
    session: AsyncSession = Depends(get_db_session),
) -> DocumentRepository:
    """Provide a `DocumentRepository` bound to the request's DB session.

    Args:
        session: The request-scoped database session.

    Returns:
        A `DocumentRepository` instance.
    """
    return DocumentRepository(session)


async def get_chunk_repository(
    session: AsyncSession = Depends(get_db_session),
) -> ChunkRepository:
    """Provide a `ChunkRepository` bound to the request's DB session.

    Args:
        session: The request-scoped database session.

    Returns:
        A `ChunkRepository` instance.
    """
    return ChunkRepository(session)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    user_repository: UserRepository = Depends(get_user_repository),
) -> User:
    """Resolve the authenticated user from a Bearer access token.

    Args:
        credentials: The `Authorization: Bearer <token>` header, extracted
            automatically by FastAPI's `HTTPBearer` scheme.
        user_repository: Repository used to look up the user record.

    Returns:
        The authenticated `User` entity.

    Raises:
        ValidationError: If the token is invalid, expired, or the user is inactive.
        NotFoundError: If the token references a user that no longer exists.
    """
    payload = decode_token(credentials.credentials, expected_type=TokenType.ACCESS)
    user_id = uuid.UUID(payload["sub"])

    user = await user_repository.get_by_id(user_id)
    if user is None:
        raise NotFoundError("User associated with this token no longer exists")
    if not user.is_active:
        raise ValidationError("This account has been deactivated")

    return user
