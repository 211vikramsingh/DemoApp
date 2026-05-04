from __future__ import annotations
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession, AsyncEngine, async_sessionmaker, create_async_engine
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


# Lazy engine — created on first access so imports don't require asyncpg/DB running.
_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker | None = None


def _get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=getattr(settings, 'debug', False),
            pool_pre_ping=True,
        )
    return _engine


def _get_session_maker() -> async_sessionmaker:
    global _session_maker
    if _session_maker is None:
        _session_maker = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_maker


# Convenience aliases used by main.py lifespan
@property  # type: ignore[misc]
def engine() -> AsyncEngine:
    return _get_engine()


AsyncSessionLocal = property(lambda _: _get_session_maker())  # type: ignore[assignment]


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with _get_session_maker()() as session:
        yield session


async def create_tables() -> None:
    """Create all tables on startup (dev only; use alembic for production)."""
    async with _get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
