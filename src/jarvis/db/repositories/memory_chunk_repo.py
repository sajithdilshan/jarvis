"""Storage for memory_chunks — the rebuildable pgvector index."""

from __future__ import annotations

from sqlalchemy import func, select, update
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
            MemoryChunk.observation_count,
            MemoryChunk.extra,
            MemoryChunk.created_at,
            MemoryChunk.updated_at,
            score,
        )
        if category is not None:
            stmt = stmt.where(MemoryChunk.category == category)
        stmt = stmt.order_by(MemoryChunk.embedding.cosine_distance(qvec)).limit(limit)
        async with self._sm() as session:
            rows = (await session.execute(stmt)).mappings().all()
        return [dict(r) for r in rows]

    # confidence is derived from how often a fact is observed: 1 - 0.5^count.
    @staticmethod
    def _confidence(count):
        return 1 - func.power(0.5, count)

    async def upsert(
        self,
        *,
        chunk_id: str,
        content: str,
        embedding: list[float],
        category: str,
        entities: list[str],
        importance: str,
        session_id: str,
        extra: dict,
    ) -> None:
        """Insert a new chunk, or bump it as a re-observation if the id already exists
        (byte-identical content collides on the deterministic id)."""
        stmt = insert(MemoryChunk).values(
            id=chunk_id,
            content=content,
            embedding=embedding,
            category=category,
            entities=entities,
            importance=importance,
            confidence=0.5,
            observation_count=1,
            session_id=session_id,
            extra=extra,
        )
        next_count = MemoryChunk.observation_count + 1
        stmt = stmt.on_conflict_do_update(
            index_elements=[MemoryChunk.id],
            set_={
                "importance": stmt.excluded.importance,
                "observation_count": next_count,
                "confidence": self._confidence(next_count),
                "extra": stmt.excluded.extra,
                "updated_at": func.now(),
            },
        )
        async with self._sm() as session, session.begin():
            await session.execute(stmt)

    async def bump_observation(self, chunk_id: str) -> None:
        """Record another observation of an existing fact (matched semantically, not by
        id): increment the count, recompute confidence, keep the canonical content."""
        next_count = MemoryChunk.observation_count + 1
        stmt = (
            update(MemoryChunk)
            .where(MemoryChunk.id == chunk_id)
            .values(
                observation_count=next_count,
                confidence=self._confidence(next_count),
                updated_at=func.now(),
            )
        )
        async with self._sm() as session, session.begin():
            await session.execute(stmt)
