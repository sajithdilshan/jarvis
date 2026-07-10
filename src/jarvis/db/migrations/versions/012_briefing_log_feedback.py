"""add briefing_log_feedback for priority-correctness ratings

Revision ID: 012
Revises: 011
Create Date: 2026-07-10

Captures the user's rating of whether the synthesizer's priority call
(high/normal/low) on a briefing entry was correct. This is the verifier signal
for the self-improving priority harness (see tmp/harness_improvement_plan.md).

Snapshots (rated_priority/source/category/narrative_snapshot) are frozen AT
RATING TIME because briefing_log rows are upserted/re-emitted across polls and
can refresh priority/category/refs — so the live row may differ from what the
user actually saw and rated.
"""

from __future__ import annotations

from alembic import op

revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS briefing_log_feedback (
            id                 BIGSERIAL PRIMARY KEY,
            briefing_id        TEXT NOT NULL,
            score              SMALLINT NOT NULL CHECK (score BETWEEN 1 AND 5),
            comment            TEXT,
            rated_priority     TEXT NOT NULL,
            source             TEXT NOT NULL,
            category           TEXT NOT NULL,
            narrative_snapshot TEXT NOT NULL,
            session_id         TEXT NOT NULL,
            created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_briefing_feedback_briefing_id
            ON briefing_log_feedback (briefing_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_briefing_feedback_source_cat
            ON briefing_log_feedback (source, category)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS briefing_log_feedback")
