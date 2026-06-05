"""add briefing_log table for the briefing stream UI

Revision ID: 003
Revises: 002
Create Date: 2026-05-30
"""

from __future__ import annotations

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS briefing_log (
            id              TEXT PRIMARY KEY,
            tier            TEXT NOT NULL DEFAULT 'noticed',
            narrative       TEXT NOT NULL,
            source          TEXT NOT NULL,
            refs            JSONB NOT NULL DEFAULT '[]',
            context         JSONB,
            ts              TIMESTAMPTZ NOT NULL,
            priority        TEXT NOT NULL DEFAULT 'normal',
            permission_ref  TEXT,
            session_id      TEXT NOT NULL,
            resolved_at     TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS briefing_log_active_idx
            ON briefing_log (resolved_at) WHERE resolved_at IS NULL
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS briefing_log_ts_idx
            ON briefing_log (ts DESC)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS briefing_log")
