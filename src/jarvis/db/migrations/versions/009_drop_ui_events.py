"""drop ui_events — UI feed now refetched via /view-model on a feed_refresh ping

Revision ID: 009
Revises: 008
Create Date: 2026-06-03

ui_events was an out-of-band spill buffer for NOTIFY payloads over the 8KB cap — only
the full feed patch ever hit it. The feed is no longer streamed: briefing_log is the
source of truth and clients refetch /view-model when a tiny feed_refresh ping arrives,
so every wire envelope is small and the spill buffer is dead. Downgrade recreates it.
"""

from __future__ import annotations

from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ui_events")


def downgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ui_events (
            id          BIGSERIAL PRIMARY KEY,
            session_id  TEXT NOT NULL,
            envelope    JSONB NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
