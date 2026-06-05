"""reshape interactions table for conversation history

Revision ID: 002
Revises: 001
Create Date: 2026-05-30
"""

from __future__ import annotations

from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS interactions")
    op.execute("""
        CREATE TABLE interactions (
            id          BIGSERIAL PRIMARY KEY,
            session_id  TEXT NOT NULL,
            role        TEXT NOT NULL,
            content     TEXT NOT NULL,
            metadata    JSONB NOT NULL DEFAULT '{}',
            timestamp   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX interactions_session_idx
            ON interactions (session_id, timestamp)
    """)
    op.execute("""
        CREATE INDEX interactions_timestamp_idx
            ON interactions (timestamp DESC)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS interactions")
    op.execute("""
        CREATE TABLE interactions (
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
        CREATE INDEX interactions_session_idx
            ON interactions (session_id, timestamp)
    """)
