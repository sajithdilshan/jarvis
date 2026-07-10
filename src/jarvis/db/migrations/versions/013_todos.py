"""add todos table for the todo-list pane

Revision ID: 013
Revises: 012
Create Date: 2026-07-10

A simple user todo list rendered in the right pane when chat is minimized.
Completing a todo is a soft delete (completed=true); only incomplete todos are
fetched. The index supports the incomplete-ordered-by-due-date read path.
"""

from __future__ import annotations

from alembic import op

revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS todos (
            id          BIGSERIAL PRIMARY KEY,
            title       TEXT NOT NULL,
            description TEXT,
            due_date    TIMESTAMPTZ,
            completed   BOOLEAN NOT NULL DEFAULT FALSE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_todos_incomplete_due
            ON todos (completed, due_date)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS todos")
