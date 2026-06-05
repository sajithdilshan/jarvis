"""Storage for progress rows + the pg_notify send (LISTEN side stays in the relay)."""

from __future__ import annotations

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from jarvis.db.tables import Progress


class ProgressRepo:
    def __init__(self, sessionmaker: async_sessionmaker):
        self._sm = sessionmaker

    async def add_and_notify(
        self, session_id: str, status: str, data: dict | None, channel: str, payload: str
    ) -> None:
        """Insert a progress row and pg_notify in the same transaction."""
        async with self._sm() as session, session.begin():
            await session.execute(
                insert(Progress).values(session_id=session_id, status=status, data=data)
            )
            await session.execute(select(func.pg_notify(channel, payload)))

    async def list_for_session(self, session_id: str) -> list[dict]:
        stmt = (
            select(Progress.status, Progress.data, Progress.timestamp)
            .where(Progress.session_id == session_id)
            .order_by(Progress.timestamp.asc())
        )
        async with self._sm() as session:
            rows = (await session.execute(stmt)).mappings().all()
        return [dict(r) for r in rows]
