"""Isolated async database for the federation package.

A separate declarative Base, engine and session factory are used so that the
federation platform's own tables never interfere with the Phase 1-5 schema and
so that the package can be validated in isolation (in-memory SQLite by default).
"""

from collections.abc import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.federation.config import settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


class FederationBase(DeclarativeBase):
    metadata = metadata
    __mapper_args__ = {"eager_defaults": True}


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_federation_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a federation DB session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_federation_db() -> None:
    """Create federation tables (imports models so they register on metadata)."""
    from src.federation import models as _models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(FederationBase.metadata.create_all)


async def dispose_federation_engine() -> None:
    await engine.dispose()
