"""pg_notify send for UI envelopes (feed_refresh / chat_token).

All UI envelopes are small, so this is a plain NOTIFY — no spill buffer. The feed
itself is never sent over the wire; clients refetch /view-model on feed_refresh.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker


class UIRepo:
    def __init__(self, sessionmaker: async_sessionmaker):
        self._sm = sessionmaker

    async def notify(self, channel: str, payload: str) -> None:
        async with self._sm() as session, session.begin():
            await session.execute(select(func.pg_notify(channel, payload)))
