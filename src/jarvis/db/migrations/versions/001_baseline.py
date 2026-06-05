"""baseline schema

Revision ID: 001
Revises: None
Create Date: 2026-05-30
"""

from __future__ import annotations

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute("""
        CREATE TABLE IF NOT EXISTS raw_data (
            id          TEXT PRIMARY KEY,
            source      TEXT NOT NULL,
            source_id   TEXT NOT NULL,
            timestamp   TIMESTAMPTZ NOT NULL,
            fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            data        JSONB NOT NULL,
            metadata    JSONB NOT NULL DEFAULT '{}'
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS memory_chunks (
            id          TEXT PRIMARY KEY,
            content     TEXT NOT NULL,
            embedding   VECTOR(768) NOT NULL,
            source      TEXT,
            category    TEXT,
            entities    TEXT[] NOT NULL DEFAULT '{}',
            importance  TEXT,
            confidence  REAL,
            extra       JSONB NOT NULL DEFAULT '{}',
            raw_data_id TEXT REFERENCES raw_data(id) ON DELETE SET NULL,
            session_id  TEXT,
            ttl_days    INT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS memory_chunks_embedding_idx
            ON memory_chunks USING hnsw (embedding vector_cosine_ops)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS memory_chunks_category_idx
            ON memory_chunks (category)
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id  TEXT PRIMARY KEY,
            trigger     TEXT NOT NULL,
            started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at TIMESTAMPTZ,
            user_request TEXT,
            agents_invoked TEXT[] NOT NULL DEFAULT '{}',
            summary     TEXT,
            view_model  JSONB,
            memory_entries_created INT NOT NULL DEFAULT 0
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS dashboard_state (
            id          TEXT PRIMARY KEY,
            view_model  JSONB NOT NULL DEFAULT '{"regions": {}}',
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS token_usage (
            id              BIGSERIAL PRIMARY KEY,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            session_id      TEXT,
            trigger         TEXT,
            activity        TEXT NOT NULL,
            agent           TEXT,
            model           TEXT NOT NULL,
            input_tokens        INT NOT NULL DEFAULT 0,
            output_tokens       INT NOT NULL DEFAULT 0,
            cache_read_tokens   INT NOT NULL DEFAULT 0,
            cache_write_tokens  INT NOT NULL DEFAULT 0,
            requests        INT NOT NULL DEFAULT 0,
            tool_calls      INT NOT NULL DEFAULT 0
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS token_usage_created_idx
            ON token_usage (created_at)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS token_usage_model_idx
            ON token_usage (model, created_at)
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS progress (
            id          BIGSERIAL PRIMARY KEY,
            session_id  TEXT NOT NULL,
            status      TEXT NOT NULL,
            data        JSONB,
            timestamp   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS progress_session_idx
            ON progress (session_id, timestamp)
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS ui_events (
            id          BIGSERIAL PRIMARY KEY,
            session_id  TEXT NOT NULL,
            envelope    JSONB NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS interactions (
            id          BIGSERIAL PRIMARY KEY,
            session_id  TEXT NOT NULL,
            action      TEXT NOT NULL,
            item_id     TEXT,
            item_type   TEXT,
            metadata    JSONB NOT NULL DEFAULT '{}',
            timestamp   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS interactions_session_idx
            ON interactions (session_id, timestamp)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS interactions")
    op.execute("DROP TABLE IF EXISTS ui_events")
    op.execute("DROP TABLE IF EXISTS progress")
    op.execute("DROP TABLE IF EXISTS token_usage")
    op.execute("DROP TABLE IF EXISTS dashboard_state")
    op.execute("DROP TABLE IF EXISTS sessions")
    op.execute("DROP TABLE IF EXISTS memory_chunks")
    op.execute("DROP TABLE IF EXISTS raw_data")
    op.execute("DROP EXTENSION IF EXISTS vector")
