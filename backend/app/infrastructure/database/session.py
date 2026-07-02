"""Async SQLAlchemy engine and session factory.

This module owns the single database engine for the application. All
repositories obtain sessions through `get_db_session`, which is wired as a
FastAPI dependency, ensuring proper connection pooling and automatic
rollback on error.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """Declarative base class for all ORM models in the application."""


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the singleton async SQLAlchemy engine, creating it if needed.

    Returns:
        The application's `AsyncEngine` instance.
    """
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
        logger.info("Database engine created for host=%s", settings.postgres_host)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the singleton session factory, creating it if needed.

    Returns:
        An `async_sessionmaker` bound to the application engine.
    """
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session per request.

    Rolls back the transaction automatically if an exception propagates,
    and always closes the session at the end of the request lifecycle.

    Yields:
        An `AsyncSession` scoped to a single request.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_connection() -> bool:
    """Verify database connectivity for health checks.

    Returns:
        True if a trivial query succeeds, False otherwise.
    """
    from sqlalchemy import text

    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("Database health check failed")
        return False
