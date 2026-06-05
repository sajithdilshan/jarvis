"""Memory and raw-data schemas (Postgres + pgvector)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MemoryMetadata(BaseModel):
    source: str  # "gmail", "slack", "github", "user", "agent"
    category: str  # "communication", "task", "decision", "preference"
    entities: list[str] = Field(default_factory=list)
    timestamp: datetime
    session_id: str
    raw_data_id: str | None = None  # FK to raw_data.id for full content
    importance: Literal["low", "medium", "high"] = "medium"
    ttl_days: int | None = None


class MemoryChunk(BaseModel):
    id: str
    content: str  # embedded text (embedding stored alongside in DB)
    metadata: MemoryMetadata


class RawDataEntry(BaseModel):
    id: str  # deterministic: f"{source}:{source_id}"
    source: str
    source_id: str
    timestamp: datetime
    fetched_at: datetime
    data: dict  # full raw payload from MCP tool
    metadata: dict = Field(default_factory=dict)  # sender, channel, repo, labels, etc.
