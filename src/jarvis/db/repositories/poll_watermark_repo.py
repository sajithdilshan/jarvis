"""Storage for poll_watermark — the last successful scheduled poll's start time."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from jarvis.db.tables import PollWatermark

# Single canonical row — there is one scheduled poll loop.
_ROW_ID = "scheduled"


class PollWatermarkRepo:
    def __init__(self, sessionmaker: async_sessionmaker):
        self._sm = sessionmaker

    async def get(self) -> datetime | None:
        async with self._sm() as session:
            return await session.scalar(
                select(PollWatermark.last_successful_run_timestamp).where(
                    PollWatermark.id == _ROW_ID
                )
            )

    async def set(self, ts: datetime) -> None:
        """Upsert the watermark to ``ts`` (the start time of a successful poll)."""
        async with self._sm() as session, session.begin():
            stmt = insert(PollWatermark).values(id=_ROW_ID, last_successful_run_timestamp=ts)
            stmt = stmt.on_conflict_do_update(
                index_elements=[PollWatermark.id],
                set_={"last_successful_run_timestamp": stmt.excluded.last_successful_run_timestamp},
            )
            await session.execute(stmt)
