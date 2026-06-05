"""add per-permission max_matches override for the circuit breaker

Revision ID: 006
Revises: 005
Create Date: 2026-05-31

max_matches semantics:
  NULL -> use the engine default (MAX_MATCHES_PER_PERMISSION)
  N>0  -> cap this rule at N matches per poll
  0    -> unlimited (no circuit breaker for this rule)
"""

from __future__ import annotations

from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE permissions ADD COLUMN IF NOT EXISTS max_matches INTEGER")


def downgrade() -> None:
    op.execute("ALTER TABLE permissions DROP COLUMN IF EXISTS max_matches")
