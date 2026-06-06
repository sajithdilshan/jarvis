"""memory_chunks: add observation_count, drop dead source/raw_data_id columns

Revision ID: 011
Revises: 010
Create Date: 2026-06-06

observation_count is now a real column (was a never-written key in extra JSONB). It
counts how many times a fact has been observed; semantic dedup on store bumps it and
derives confidence from it. The source and raw_data_id columns were never populated by
the store path and had no readers, so they're dropped.
"""

from __future__ import annotations

from alembic import op

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE memory_chunks "
        "ADD COLUMN IF NOT EXISTS observation_count INT NOT NULL DEFAULT 1"
    )
    op.execute("ALTER TABLE memory_chunks DROP COLUMN IF EXISTS source")
    op.execute("ALTER TABLE memory_chunks DROP COLUMN IF EXISTS raw_data_id")


def downgrade() -> None:
    op.execute("ALTER TABLE memory_chunks ADD COLUMN IF NOT EXISTS source TEXT")
    op.execute(
        "ALTER TABLE memory_chunks ADD COLUMN IF NOT EXISTS raw_data_id TEXT "
        "REFERENCES raw_data(id) ON DELETE SET NULL"
    )
    op.execute("ALTER TABLE memory_chunks DROP COLUMN IF EXISTS observation_count")
