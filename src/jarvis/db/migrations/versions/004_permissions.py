"""add permissions table for standing automation rules

Revision ID: 004
Revises: 003
Create Date: 2026-05-30
"""

from __future__ import annotations

from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS permissions (
            id              TEXT PRIMARY KEY,
            description     TEXT NOT NULL,
            source          TEXT,
            constraints     JSONB NOT NULL DEFAULT '{}',
            allowed_actions TEXT[] NOT NULL DEFAULT '{}',
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_via     TEXT,
            active          BOOLEAN NOT NULL DEFAULT true
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS permissions_active_idx
            ON permissions (active) WHERE active = true
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS permissions")
