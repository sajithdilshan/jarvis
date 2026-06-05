"""Storage for token_usage telemetry."""

from __future__ import annotations

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from jarvis.db.tables import TokenUsage


class TokenUsageRepo:
    def __init__(self, sessionmaker: async_sessionmaker):
        self._sm = sessionmaker

    async def record(self, **fields) -> None:
        """Insert one usage row. ``fields`` are TokenUsage column kwargs."""
        async with self._sm() as session, session.begin():
            await session.execute(insert(TokenUsage).values(**fields))
