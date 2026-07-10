"""TodoService — thin CRUD layer over TodoRepo for the todo-list pane.

Returns dicts (model_dump) for the API routes, matching PermissionService.
"""

from __future__ import annotations

from datetime import datetime

from jarvis.db.repositories.todo_repo import _UNSET, TodoRepo
from jarvis.models.todo import TodoCreate


class TodoService:
    def __init__(self, repo: TodoRepo):
        self._repo = repo

    async def list_incomplete(self) -> list[dict]:
        return [r.model_dump() for r in await self._repo.list_incomplete()]

    async def create(
        self,
        title: str,
        description: str | None = None,
        due_date: datetime | None = None,
    ) -> dict:
        record = await self._repo.insert(
            TodoCreate(title=title, description=description, due_date=due_date)
        )
        return record.model_dump()

    async def update(
        self,
        todo_id: int,
        title: str | None = None,
        description: str | None = None,
        due_date: datetime | None | object = _UNSET,
    ) -> dict | None:
        """Partial update. due_date uses a sentinel since None clears the date."""
        record = await self._repo.apply_partial_update(
            todo_id,
            title=title,
            description=description,
            due_date=due_date,
        )
        return record.model_dump() if record else None

    async def complete(self, todo_id: int) -> bool:
        """Mark a todo complete (soft delete). Returns False if not found."""
        return await self._repo.set_completed(todo_id, True)

    async def delete(self, todo_id: int) -> bool:
        """Permanently remove a todo. Returns False if not found."""
        return await self._repo.delete(todo_id)
