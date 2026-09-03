"""Shared fixtures for federation/IAM tests.

Provides an in-memory SQLite-backed federation database, seeded with the IAM
baseline (departments, roles, permissions, admin officer). Because the global
``AsyncSessionLocal`` is bound to the configured engine, tests here build their
own engine/sessionmaker against ``sqlite+aiosqlite:///:memory:``.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import uuid

from sqlalchemy import MetaData

from src.federation.db import FederationBase
from src.federation.iam_seed import seed as run_seed

# Tables (from the app Base) used by the Phase 6.2 core-security modules. A
# filtered subset is used because the full app metadata contains JSONB columns
# that the SQLite test backend cannot compile.
_SECURITY_TABLES = {
    "users",
    "refresh_tokens",
    "user_security",
    "password_history",
    "login_attempts",
    "mfa_recovery_codes",
    "trusted_devices",
    "security_events",
    "security_threats",
}


@pytest.fixture
async def security_db():
    """In-memory SQLite DB with the core-auth + security tables only."""
    from src.models.base import Base

    md = MetaData()
    for name, table in Base.metadata.tables.items():
        if name in _SECURITY_TABLES:
            table.to_metadata(md)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", pool_pre_ping=True)
    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(md.create_all)
    async with Session() as db:
        yield db
        await db.close()
    await engine.dispose()


@pytest.fixture
async def security_user(security_db):
    """A fresh core-auth user plus its id (for security module tests)."""
    from src.core.security import hash_password
    from src.models.user import User

    user = User(
        email=f"user-{uuid.uuid4().hex[:10]}@sentinel.gp",
        full_name="Security Test User",
        password_hash=hash_password("Abcdef1!a1"),
    )
    security_db.add(user)
    await security_db.flush()
    return user


@pytest.fixture
async def fed_db():
    """Yield a session bound to a fresh in-memory federation DB."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", pool_pre_ping=True)
    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(FederationBase.metadata.create_all)
    async with Session() as db:
        await run_seed(db)
        yield db
        await db.close()
    await engine.dispose()
