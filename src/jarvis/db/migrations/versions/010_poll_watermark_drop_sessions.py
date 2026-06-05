"""add poll_watermark, drop sessions

Revision ID: 010
Revises: 009
Create Date: 2026-06-03

The scheduled poll window is now anchored on a dedicated single-row poll_watermark
(the last *successful* run's start time), advanced only on a failure-free run. This
replaces the old derivation from sessions.finished_at; the sessions audit table had no
remaining readers (memory storage moved off it), so it's dropped.
"""

from __future__ import annotations

from alembic import op

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS poll_watermark (
            id                            TEXT PRIMARY KEY,
            last_successful_run_timestamp TIMESTAMPTZ
        )
        """
    )
    # Seed from the most recent finished session so the first post-migration poll
    # doesn't re-scan a full 24h window (best-effort; sessions may already be gone).
    op.execute(
        """
        INSERT INTO poll_watermark (id, last_successful_run_timestamp)
        SELECT 'scheduled', MAX(finished_at)
        FROM sessions
        WHERE finished_at IS NOT NULL
        ON CONFLICT (id) DO NOTHING
        """
    )
    op.execute("DROP TABLE IF EXISTS sessions")


def downgrade() -> None:
    op.execute(
        """
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
        """
    )
    op.execute("DROP TABLE IF EXISTS poll_watermark")
