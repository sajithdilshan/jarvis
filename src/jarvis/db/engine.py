"""SQLAlchemy async engine + session factory (one engine per process).

All CRUD goes through the engine/sessionmaker. A separate thin asyncpg pool
(``notify_pool``) survives only for the WebSocket relay's LISTEN/NOTIFY, which
the SQLAlchemy ORM does not expose (see api/websocket.py).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import asyncpg
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_ALEMBIC_INI = Path(__file__).parents[3] / "alembic.ini"


def _sqla_url(dsn: str) -> str:
    """Convert a plain libpq DSN to the asyncpg-driver URL SQLAlchemy expects."""
    return dsn.replace("postgresql://", "postgresql+asyncpg://")


def _run_alembic_upgrade(dsn: str) -> None:
    """Run alembic upgrade head synchronously (called via to_thread)."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", _sqla_url(dsn))
    command.upgrade(cfg, "head")


async def _bootstrap(dsn: str) -> None:
    """Run Alembic migrations to ensure the schema is up to date."""
    await asyncio.to_thread(_run_alembic_upgrade, dsn)


def create_engine(dsn: str, *, max_size: int = 10) -> AsyncEngine:
    """Create the async engine. The ORM's ``pgvector.sqlalchemy.Vector`` column type
    handles ``list[float]`` <-> ``vector`` serialization itself, so we must NOT register
    the raw asyncpg vector codec here — doing so double-encodes and asyncpg then fails
    to parse the already-stringified vector."""
    return create_async_engine(
        _sqla_url(dsn),
        pool_size=max_size,
        max_overflow=0,
        pool_pre_ping=True,
    )


async def engine_resource(dsn: str, max_size: int = 10):
    """DI Resource: migrate, build the engine, yield (engine, sessionmaker), dispose."""
    await _bootstrap(dsn)
    engine = create_engine(dsn, max_size=max_size)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        yield sessionmaker
    finally:
        await engine.dispose()


async def notify_pool_resource(dsn: str, min_size: int = 1, max_size: int = 4):
    """DI Resource: a thin asyncpg pool used ONLY for LISTEN/NOTIFY in the relay.

    Schema bootstrap is owned by ``engine_resource``; this just opens connections.
    """
    pool = await asyncpg.create_pool(dsn, min_size=min_size, max_size=max_size)
    try:
        yield pool
    finally:
        await pool.close()
