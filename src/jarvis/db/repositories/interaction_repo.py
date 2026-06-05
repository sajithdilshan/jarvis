"""Storage for interactions — conversation history."""

from __future__ import annotations

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from jarvis.db.tables import Interaction


class InteractionRepo:
    def __init__(self, sessionmaker: async_sessionmaker):
        self._sm = sessionmaker

    async def add(self, session_id: str, role: str, content: str, metadata: dict) -> None:
        async with self._sm() as session, session.begin():
            await session.execute(
                insert(Interaction).values(
                    session_id=session_id,
                    role=role,
                    content=content,
                    metadata_=metadata,
                )
            )

    async def recent(self, limit: int) -> list[dict]:
        """Most recent ``limit`` interactions, returned oldest-first."""
        stmt = (
            select(
                Interaction.session_id,
                Interaction.role,
                Interaction.content,
                Interaction.timestamp,
            )
            .order_by(Interaction.timestamp.desc())
            .limit(limit)
        )
        async with self._sm() as session:
            rows = (await session.execute(stmt)).mappings().all()
        return [dict(r) for r in reversed(rows)]

    async def recent_messages(self, limit: int, before_id: int | None = None) -> list[dict]:
        """Chat thread page: ``{id, role, text, ts}`` oldest-first, skipping blanks.

        Newest ``limit`` messages by default; pass ``before_id`` to page backwards
        (returns the messages immediately older than that cursor).
        """
        stmt = select(
            Interaction.id,
            Interaction.role,
            Interaction.content,
            Interaction.timestamp,
        )
        if before_id is not None:
            stmt = stmt.where(Interaction.id < before_id)
        stmt = stmt.order_by(Interaction.timestamp.desc()).limit(limit)
        async with self._sm() as session:
            rows = (await session.execute(stmt)).all()
        return [
            {"id": id_, "role": role, "text": content, "ts": ts.isoformat()}
            for id_, role, content, ts in reversed(rows)
            if content
        ]
