"""add briefing_log.category for UI grouping (did / ask / noticed)

Revision ID: 007
Revises: 006
Create Date: 2026-06-02

category is independent of tier: it drives which sidebar section an entry lands in.
  'did'     -> an autonomous action was taken
  'ask'     -> needs a user decision (e.g. permission overflow, action failure)
  'noticed' -> an observation (default)
Persisted so it survives carry-forward when a scheduled rebuild reconstructs nodes
from briefing_log (tier alone can't recover 'ask' vs 'noticed').
"""

from __future__ import annotations

from alembic import op

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE briefing_log ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'noticed'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE briefing_log DROP COLUMN IF EXISTS category")
