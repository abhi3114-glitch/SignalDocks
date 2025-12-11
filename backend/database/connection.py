"""
SignalDock Database Connection Management
"""
import asyncio
import sys
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import logging

from .models import Base

logger = logging.getLogger(__name__)

# Engine and session factory (initialized lazily)
_engine = None
_async_session_factory = None


def _get_config():
    """Import config lazily to avoid circular imports"""
    # Add parent directory to path if not already there
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    from config import get_config
    return get_config()


def get_engine():
    """Get or create the database engine"""
    global _engine
    if _engine is None:
        config = _get_config()
        _engine = create_async_engine(
            config.database.database_url,
            echo=config.debug,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
    return _engine


def get_session_factory():
    """Get or create the session factory"""
    global _async_session_factory
    if _async_session_factory is None:
        engine = get_engine()
        _async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False
        )
    return _async_session_factory


def AsyncSessionLocal():
    """Get session factory (for backward compatibility)"""
    return get_session_factory()


async def init_db() -> None:
    """Initialize database and create tables"""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized successfully")


async def drop_db() -> None:
    """Drop all tables (use with caution)"""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.warning("All database tables dropped")


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session context manager"""
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI endpoints"""
    async with get_db() as session:
        yield session


async def close_db() -> None:
    """Close database connections"""
    global _engine, _async_session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None
    logger.info("Database connections closed")
