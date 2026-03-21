from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.orm import declarative_base, DeclarativeMeta
from sqlalchemy.pool import NullPool, QueuePool
from contextlib import asynccontextmanager
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Create base class for models
Base: DeclarativeMeta = declarative_base()

# Global engine and sessionmaker
_engine: Optional[AsyncEngine] = None
_async_session_maker: Optional[async_sessionmaker] = None


async def init_db() -> None:
    """Initialize database connection pool and create tables."""
    global _engine, _async_session_maker
    
    # Configure engine with appropriate pool settings
    if settings.app_env == "test":
        pool_class = NullPool
    else:
        # For async engine, use NullPool to avoid issues
        pool_class = NullPool
    
    _engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
        poolclass=pool_class,
        pool_pre_ping=True,  # Verify connections before using
        pool_recycle=3600,   # Recycle connections after 1 hour
    )
    
    _async_session_maker = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    # Create tables if they don't exist (for development)
    if settings.app_env == "development":
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database initialized successfully")


async def close_db() -> None:
    """Close database connection pool."""
    global _engine
    if _engine:
        await _engine.dispose()
        logger.info("Database connection pool closed")


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    if not _async_session_maker:
        await init_db()
    
    async with _async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database sessions."""
    if not _async_session_maker:
        await init_db()
    
    async with _async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()