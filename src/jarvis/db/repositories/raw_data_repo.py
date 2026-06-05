"""Storage for raw_data — the source of truth for full payloads."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from jarvis.db.tables import RawData


class RawDataRepo:
    def __init__(self, sessionmaker: async_sessionmaker):
        self._sm = sessionmaker

    async def upsert(
        self,
        *,
        id: str,
        source: str,
        source_id: str,
        timestamp: datetime,
        fetched_at: datetime,
        data: dict,
        metadata: dict,
    ) -> None:
        stmt = insert(RawData).values(
            id=id,
            source=source,
            source_id=source_id,
            timestamp=timestamp,
            fetched_at=fetched_at,
            data=data,
            metadata_=metadata,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[RawData.id],
            set_={
                "data": stmt.excluded.data,
                "metadata": stmt.excluded.metadata,
                "fetched_at": stmt.excluded.fetched_at,
            },
        )
        async with self._sm() as session, session.begin():
            await session.execute(stmt)
