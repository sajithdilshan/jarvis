"""add executed_permissions_audit table — queryable trail of permission executions

Revision ID: 005
Revises: 004
Create Date: 2026-05-31
"""

from __future__ import annotations

from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS executed_permissions_audit (
            id              BIGSERIAL PRIMARY KEY,
            permission_id   TEXT NOT NULL,
            permission_desc TEXT NOT NULL,
            session_id      TEXT NOT NULL,
            source          TEXT NOT NULL,
            item_id         TEXT NOT NULL,
            tool            TEXT NOT NULL,
            status          TEXT NOT NULL,        -- done | skipped | failed
            detail          TEXT,
            ts              TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS exec_perm_audit_perm_idx
            ON executed_permissions_audit (permission_id, ts DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS exec_perm_audit_session_idx
            ON executed_permissions_audit (session_id)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS executed_permissions_audit")
