"""Typed contracts for todo-list items."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TodoCreate(BaseModel):
    title: str
    description: str | None = None
    due_date: datetime | None = None


class TodoUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    due_date: datetime | None = None


class TodoRecord(BaseModel):
    id: int
    title: str
    description: str | None = None
    due_date: str | None = None
    completed: bool = False
    created_at: str | None = None


def todo_record_from_row(row) -> TodoRecord:
    return TodoRecord(
        id=row.id,
        title=row.title,
        description=row.description,
        due_date=row.due_date.isoformat() if row.due_date else None,
        completed=row.completed,
        created_at=row.created_at.isoformat() if row.created_at else None,
    )
