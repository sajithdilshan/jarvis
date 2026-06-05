"""Storage for memory_chunks — the rebuildable pgvector index."""

from __future__ import annotations

from sqlalchemy import Integer, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from jarvis.db.tables import MemoryChunk


class MemoryChunkRepo:
    def __init__(self, sessionmaker: async_sessionmaker):
        self._sm = sessionmaker

    async def search_by_embedding(
        self, qvec: list[float], limit: int, category: str | None
    ) -> list[dict]:
        """Cosine-distance nearest neighbours; returns rows + a 0..1 ``score``."""
        score = (1 - MemoryChunk.embedding.cosine_distance(qvec)).label("score")
        stmt = select(
            MemoryChunk.id,
            MemoryChunk.content,
            MemoryChunk.category,
            MemoryChunk.entities,
            MemoryChunk.importance,
            MemoryChunk.confidence,
            MemoryChunk.raw_data_id,
            MemoryChunk.extra,
            MemoryChunk.created_at,
            MemoryChunk.updated_at,
            MemoryChunk.extra["observation_count"].astext.cast(Integer).label("observation_count"),
            score,
        )
        if category is not None:
            stmt = stmt.where(MemoryChunk.category == category)
        stmt = stmt.order_by(MemoryChunk.embedding.cosine_distance(qvec)).limit(limit)
        async with self._sm() as session:
            rows = (await session.execute(stmt)).mappings().all()
        return [dict(r) for r in rows]

    async def upsert(
        self,
        *,
        chunk_id: str,
        content: str,
        embedding: list[float],
        category: str,
        entities: list[str],
        importance: str,
        confidence: float | None,
        raw_data_id: str | None,
        session_id: str,
        extra: dict,
    ) -> None:
        stmt = insert(MemoryChunk).values(
            id=chunk_id,
            content=content,
            embedding=embedding,
            category=category,
            entities=entities,
            importance=importance,
            confidence=confidence,
            raw_data_id=raw_data_id,
            session_id=session_id,
            extra=extra,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[MemoryChunk.id],
            set_={
                "content": stmt.excluded.content,
                "embedding": stmt.excluded.embedding,
                "importance": stmt.excluded.importance,
                "confidence": stmt.excluded.confidence,
                "extra": stmt.excluded.extra,
                "updated_at": func.now(),
            },
        )
        async with self._sm() as session, session.begin():
            await session.execute(stmt)

    async def update_preference(
        self, chunk_id: str, confidence: float, observation_count: int
    ) -> None:
        stmt = (
            update(MemoryChunk)
            .where(MemoryChunk.id == chunk_id)
            .values(
                confidence=confidence,
                extra=MemoryChunk.extra.op("||")(
                    func.jsonb_build_object("observation_count", observation_count)
                ),
                updated_at=func.now(),
            )
        )
        async with self._sm() as session, session.begin():
            await session.execute(stmt)
