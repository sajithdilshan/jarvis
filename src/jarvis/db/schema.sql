-- Jarvis schema — reference DDL (current state).
-- Migrations are managed by Alembic (see migrations/versions/).
-- This file is kept as documentation; do NOT run it directly.

CREATE EXTENSION IF NOT EXISTS vector;

-- Source of truth: full raw payloads from MCP tools.
CREATE TABLE IF NOT EXISTS raw_data (
    id          TEXT PRIMARY KEY,           -- deterministic f"{source}:{source_id}"
    source      TEXT NOT NULL,
    source_id   TEXT NOT NULL,
    timestamp   TIMESTAMPTZ NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    data        JSONB NOT NULL,             -- full payload
    metadata    JSONB NOT NULL DEFAULT '{}'
);

-- Vector memory. embedding dim MUST match embedding.dim (768 for nomic-embed-text-v1.5).
CREATE TABLE IF NOT EXISTS memory_chunks (
    id          TEXT PRIMARY KEY,
    content     TEXT NOT NULL,              -- the embedded text (lets us re-embed)
    embedding   VECTOR(768) NOT NULL,
    source      TEXT,
    category    TEXT,                       -- communication|task|decision|preference
    entities    TEXT[] NOT NULL DEFAULT '{}',
    importance  TEXT,                       -- low|medium|high
    confidence  REAL,                       -- for preferences
    extra       JSONB NOT NULL DEFAULT '{}',-- learned_from, observation_count, etc.
    raw_data_id TEXT REFERENCES raw_data(id) ON DELETE SET NULL,
    session_id  TEXT,
    ttl_days    INT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Approximate-NN index for cosine distance.
CREATE INDEX IF NOT EXISTS memory_chunks_embedding_idx
    ON memory_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS memory_chunks_category_idx ON memory_chunks (category);

-- Scheduled-poll watermark: start time of the last poll that finished with NO source
-- failures. The workflow reads it as the next run's 'since' and only advances it on a
-- clean run, so a failed source makes the next run re-cover the same window. Single row.
CREATE TABLE IF NOT EXISTS poll_watermark (
    id                            TEXT PRIMARY KEY,   -- always 'scheduled'
    last_successful_run_timestamp TIMESTAMPTZ
);

-- (Presentation layer: the dashboard feed is rebuilt on demand from unresolved
-- briefing_log rows by /view-model — there is no separate dashboard_state table.)

-- Token-usage telemetry: one row per LLM-running activity call. Operational data
-- (not cognition, not presentation) — lets us tally cost by model / agent / period.
-- Tokens only; dollar cost is computed at query time (prices change per model/region).
CREATE TABLE IF NOT EXISTS token_usage (
    id              BIGSERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    session_id      TEXT,
    trigger         TEXT,                  -- 'scheduled' | 'user_request'
    activity        TEXT NOT NULL,         -- run_sub_agent | run_main_agent_synthesize | ...
    agent           TEXT,                  -- gmail | slack | github | main | ui
    model           TEXT NOT NULL,         -- resolved model spec (bedrock:arn:...)
    input_tokens        INT NOT NULL DEFAULT 0,
    output_tokens       INT NOT NULL DEFAULT 0,
    cache_read_tokens   INT NOT NULL DEFAULT 0,
    cache_write_tokens  INT NOT NULL DEFAULT 0,
    requests        INT NOT NULL DEFAULT 0, -- LLM round-trips (tool loops)
    tool_calls      INT NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS token_usage_created_idx ON token_usage (created_at);
CREATE INDEX IF NOT EXISTS token_usage_model_idx   ON token_usage (model, created_at);

CREATE TABLE IF NOT EXISTS progress (
    id          BIGSERIAL PRIMARY KEY,
    session_id  TEXT NOT NULL,
    status      TEXT NOT NULL,
    data        JSONB,
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS progress_session_idx ON progress (session_id, timestamp);

-- (No WS spill buffer: every NOTIFY envelope is small. The feed is never sent over
-- the wire — clients refetch /view-model on a tiny feed_refresh ping.)

-- Briefing stream: the primary UI content. Entries are never deleted — only resolved.
-- Active stream: WHERE resolved_at IS NULL. History always available.
CREATE TABLE IF NOT EXISTS briefing_log (
    id              TEXT PRIMARY KEY,
    tier            TEXT NOT NULL DEFAULT 'noticed',   -- 'noticed' | 'did'
    category        TEXT NOT NULL DEFAULT 'noticed',   -- UI grouping: 'did' | 'ask' | 'noticed'
    narrative       TEXT NOT NULL,
    source          TEXT NOT NULL,                     -- 'gmail', 'github', 'slack', 'calendar'
    refs            JSONB NOT NULL DEFAULT '[]',       -- [{label, url}]
    context         JSONB,                            -- expandable detail (email body, diff, etc.)
    ts              TIMESTAMPTZ NOT NULL,             -- underlying event time
    priority        TEXT NOT NULL DEFAULT 'normal',   -- 'low' | 'normal' | 'high'
    permission_ref  TEXT,                             -- FK to permissions.id for 'did' entries
    session_id      TEXT NOT NULL,
    resolved_at     TIMESTAMPTZ,                     -- NULL = active, set = dismissed
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS briefing_log_active_idx ON briefing_log (resolved_at) WHERE resolved_at IS NULL;
CREATE INDEX IF NOT EXISTS briefing_log_ts_idx ON briefing_log (ts DESC);

-- Standing permissions: rules the agent can execute autonomously.
-- Managed via chat (grant/revoke/refine). Agent checks these during scheduled runs.
CREATE TABLE IF NOT EXISTS permissions (
    id              TEXT PRIMARY KEY,
    description     TEXT NOT NULL,                  -- natural language: "archive Jenkins spam"
    source          TEXT,                           -- 'gmail', 'github', 'slack', or NULL (any)
    constraints     JSONB NOT NULL DEFAULT '{}',    -- structured match rules
    allowed_actions TEXT[] NOT NULL DEFAULT '{}',   -- e.g. ['archive', 'mark_read']
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_via     TEXT,                           -- chat message / session that granted it
    active          BOOLEAN NOT NULL DEFAULT true
);
CREATE INDEX IF NOT EXISTS permissions_active_idx ON permissions (active) WHERE active = true;

CREATE TABLE IF NOT EXISTS interactions (
    id          BIGSERIAL PRIMARY KEY,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,          -- 'user' or 'assistant'
    content     TEXT NOT NULL,
    metadata    JSONB NOT NULL DEFAULT '{}',
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS interactions_session_idx ON interactions (session_id, timestamp);
CREATE INDEX IF NOT EXISTS interactions_timestamp_idx ON interactions (timestamp DESC);
