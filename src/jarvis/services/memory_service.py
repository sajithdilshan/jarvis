"""Memory: vector search + chunk/raw-data persistence (the embedding-aware layer).

``raw_data`` is the source of truth; ``memory_chunks`` is a rebuildable vector index
(re-embed from ``content`` if the model changes). Telemetry, interactions, briefing
and session audit live in their own services (see services/).
"""

from __future__ import annotations

import asyncio
import hashlib

from jarvis.db.repositories.memory_chunk_repo import MemoryChunkRepo
from jarvis.db.repositories.raw_data_repo import RawDataRepo
from jarvis.models.memory import RawDataEntry
from jarvis.services.embeddings import Embedder


class MemoryService:
    def __init__(self, chunk_repo: MemoryChunkRepo, raw_data_repo: RawDataRepo, embedder: Embedder):
        self._chunks = chunk_repo
        self._raw = raw_data_repo
        self._embedder = embedder

    # BGE convention: prefix the *query* for retrieval; documents are embedded as-is.
    _BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

    async def _embed(self, text: str, *, is_query: bool) -> list[float]:
        payload = f"{self._BGE_QUERY_PREFIX}{text}" if is_query else text
        vecs = await asyncio.to_thread(self._embedder.embed, [payload])
        return vecs[0]

    # --- Vector search (pgvector cosine distance) ---

    async def semantic_search(
        self, query: str, limit: int = 10, category: str | None = None
    ) -> list[dict]:
        qvec = await self._embed(query, is_query=True)
        return await self._chunks.search_by_embedding(qvec, limit, category)

    async def store_chunk(
        self,
        content: str,
        category: str,
        entities: list[str],
        importance: str,
        raw_data_id: str | None = None,
        session_id: str = "",
        extra: dict | None = None,
    ) -> str:
        chunk_id = f"{category}:{hashlib.sha1(content.encode()).hexdigest()[:16]}"
        vec = await self._embed(content, is_query=False)
        extra = extra or {}
        await self._chunks.upsert(
            chunk_id=chunk_id,
            content=content,
            embedding=vec,
            category=category,
            entities=entities,
            importance=importance,
            confidence=extra.get("confidence"),
            raw_data_id=raw_data_id or None,
            session_id=session_id,
            extra=extra,
        )
        return chunk_id

    async def update_preference(
        self, chunk_id: str, confidence: float, observation_count: int
    ) -> None:
        await self._chunks.update_preference(chunk_id, confidence, observation_count)

    # --- Raw data (source of truth) ---

    async def store_raw_data(self, entry: RawDataEntry) -> None:
        await self._raw.upsert(
            id=entry.id,
            source=entry.source,
            source_id=entry.source_id,
            timestamp=entry.timestamp,
            fetched_at=entry.fetched_at,
            data=entry.data,
            metadata=entry.metadata,
        )
