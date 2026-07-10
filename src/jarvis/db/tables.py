"""ORM mapped classes — one per table, kept in sync with db/migrations/versions.

Migrations remain the schema source of truth; these models are the query layer only
(never metadata.create_all). Column types mirror the baseline + later migrations.
"""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from jarvis.db.base import EMBED_DIM, Base


class RawData(Base):
    __tablename__ = "raw_data"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    source: Mapped[str] = mapped_column(Text)
    source_id: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    data: Mapped[dict] = mapped_column(JSONB)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class MemoryChunk(Base):
    __tablename__ = "memory_chunks"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBED_DIM))
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    entities: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    importance: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    observation_count: Mapped[int] = mapped_column(Integer, default=1)
    extra: Mapped[dict] = mapped_column(JSONB, default=dict)
    session_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    ttl_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class TokenUsage(Base):
    __tablename__ = "token_usage"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    session_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger: Mapped[str | None] = mapped_column(Text, nullable=True)
    activity: Mapped[str] = mapped_column(Text)
    agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(Text)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, default=0)
    requests: Mapped[int] = mapped_column(Integer, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)


class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class BriefingLog(Base):
    __tablename__ = "briefing_log"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tier: Mapped[str] = mapped_column(Text, server_default=text("'noticed'"))
    category: Mapped[str] = mapped_column(Text, server_default=text("'noticed'"))
    narrative: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    refs: Mapped[list] = mapped_column(JSONB, default=list)
    context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ts: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    priority: Mapped[str] = mapped_column(Text, server_default=text("'normal'"))
    permission_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_id: Mapped[str] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class BriefingLogFeedback(Base):
    """User rating of whether the synthesizer's priority call on an entry was right.

    Snapshots (rated_priority/source/category/narrative_snapshot) are frozen at
    rating time — briefing_log rows are upserted across polls and can drift from
    what the user actually saw. The improvement harness trains on these snapshots.
    """

    __tablename__ = "briefing_log_feedback"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    briefing_id: Mapped[str] = mapped_column(Text)
    score: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    rated_priority: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    narrative_snapshot: Mapped[str] = mapped_column(Text)
    session_id: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class PollWatermark(Base):
    """Single row tracking the last *successful* scheduled poll's start time.

    The scheduled workflow reads this as the 'since' for the next poll and only
    advances it when a run completes with no source failures — so a failed run leaves
    the watermark untouched and the next run re-covers the same window.
    """

    __tablename__ = "poll_watermark"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    last_successful_run_timestamp: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    constraints: Mapped[dict] = mapped_column(JSONB, default=dict)
    allowed_actions: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    # Circuit-breaker override: NULL -> engine default, 0 -> unlimited, N -> that cap.
    max_matches: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    created_via: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class ExecutedPermissionAudit(Base):
    __tablename__ = "executed_permissions_audit"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    permission_id: Mapped[str] = mapped_column(Text)
    permission_desc: Mapped[str] = mapped_column(Text)
    session_id: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    item_id: Mapped[str] = mapped_column(Text)
    tool: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    ts: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))


class Progress(Base):
    __tablename__ = "progress"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
