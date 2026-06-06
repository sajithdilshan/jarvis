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
    def __init__(
        self,
        chunk_repo: MemoryChunkRepo,
        raw_data_repo: RawDataRepo,
        embedder: Embedder,
        dedup_threshold: float = 0.92,
    ):
        self._chunks = chunk_repo
        self._raw = raw_data_repo
        self._embedder = embedder
        self._dedup_threshold = dedup_threshold

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
        session_id: str = "",
        extra: dict | None = None,
    ) -> str:
        """Store a fact. If a semantically near-identical fact already exists in the same
        category (cosine score >= dedup_threshold), treat this as a re-observation: bump
        that chunk's observation_count/confidence and keep its canonical text. Otherwise
        insert a fresh chunk. Returns the id of the stored or bumped chunk."""
        vec = await self._embed(content, is_query=False)
        neighbours = await self._chunks.search_by_embedding(vec, 1, category)
        if neighbours and neighbours[0]["score"] >= self._dedup_threshold:
            existing_id = neighbours[0]["id"]
            await self._chunks.bump_observation(existing_id)
            return existing_id
        chunk_id = f"{category}:{hashlib.sha1(content.encode()).hexdigest()[:16]}"
        await self._chunks.upsert(
            chunk_id=chunk_id,
            content=content,
            embedding=vec,
            category=category,
            entities=entities,
            importance=importance,
            session_id=session_id,
            extra=extra or {},
        )
        return chunk_id

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
