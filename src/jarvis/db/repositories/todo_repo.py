"""Storage for todos — the todo-list pane's CRUD."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from jarvis.db.tables import Todo
from jarvis.models.todo import TodoCreate, TodoRecord, todo_record_from_row

# Sentinel: "argument not supplied" — distinct from None, which is a valid value for
# due_date (None means "clear the due date").
_UNSET = object()


class TodoRepo:
    def __init__(self, sessionmaker: async_sessionmaker):
        self._sm = sessionmaker

    async def insert(self, record: TodoCreate) -> TodoRecord:
        async with self._sm() as session, session.begin():
            result = await session.execute(
                insert(Todo)
                .values(
                    title=record.title,
                    description=record.description,
                    due_date=record.due_date,
                )
                .returning(Todo)
            )
            row = result.scalar_one()
            return todo_record_from_row(row)

    async def list_incomplete(self) -> list[TodoRecord]:
        async with self._sm() as session:
            rows = (
                await session.execute(
                    select(Todo)
                    .where(Todo.completed.is_(False))
                    .order_by(Todo.due_date.asc().nullslast(), Todo.created_at.asc())
                )
            ).scalars().all()
        return [todo_record_from_row(r) for r in rows]

    async def apply_partial_update(
        self,
        todo_id: int,
        *,
        title: str | None = None,
        description: str | None = None,
        due_date: datetime | None | object = _UNSET,
    ) -> TodoRecord | None:
        """Read-modify-write in one transaction: fields left None (title/description)
        keep their current value. Returns the merged record, or None if not found.

        due_date uses a sentinel (_UNSET) since None is a valid new value (= clear it).
        """
        async with self._sm() as session, session.begin():
            row = await session.get(Todo, todo_id)
            if not row:
                return None
            if title is not None:
                row.title = title
            if description is not None:
                row.description = description
            if due_date is not _UNSET:
                row.due_date = due_date
            row.updated_at = func.now()
            await session.flush()
            await session.refresh(row)
            return todo_record_from_row(row)

    async def set_completed(self, todo_id: int, completed: bool) -> bool:
        """Flip completed state; returns True if a row was updated."""
        async with self._sm() as session, session.begin():
            result = await session.execute(
                update(Todo)
                .where(Todo.id == todo_id)
                .values(completed=completed, updated_at=func.now())
            )
        return result.rowcount == 1

    async def delete(self, todo_id: int) -> bool:
        """Hard-delete a todo; returns True if a row was removed."""
        async with self._sm() as session, session.begin():
            result = await session.execute(delete(Todo).where(Todo.id == todo_id))
        return result.rowcount == 1
