"""drop dashboard_state — /view-model now rebuilds from briefing_log

Revision ID: 008
Revises: 007
Create Date: 2026-06-03

The dashboard_state row was a denormalized cache of the unresolved briefing feed.
/view-model now rebuilds the feed straight from briefing_log (the source of truth),
so the cache is redundant and can drift. Downgrade recreates the empty table; the
next scheduled rebuild would have repopulated it under the old code path.
"""

from __future__ import annotations

from alembic import op

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS dashboard_state")


def downgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS dashboard_state (
            id          TEXT PRIMARY KEY,
            view_model  JSONB NOT NULL DEFAULT '{"regions": {}}',
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
