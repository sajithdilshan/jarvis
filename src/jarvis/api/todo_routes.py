"""Todo-list routes — CRUD for the todo pane."""

from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from jarvis.db.repositories.todo_repo import _UNSET
from jarvis.services.todo_service import TodoService


class TodoCreateRequest(BaseModel):
    title: str
    description: str | None = None
    due_date: datetime | None = None


class TodoUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    due_date: datetime | None = None


def register_todo_routes(app: FastAPI, *, todo_service: TodoService | None) -> None:
    @app.get("/todos")
    async def list_todos() -> JSONResponse:
        """List incomplete todos, ordered by due date ascending."""
        if not todo_service:
            return JSONResponse([])
        return JSONResponse(await todo_service.list_incomplete())

    @app.post("/todos")
    async def create_todo(request: TodoCreateRequest) -> dict:
        if not todo_service:
            return {"ok": False, "error": "todos not configured"}
        return await todo_service.create(
            title=request.title,
            description=request.description,
            due_date=request.due_date,
        )

    @app.patch("/todos/{todo_id}")
    async def update_todo(todo_id: int, request: TodoUpdateRequest) -> dict:
        if not todo_service:
            return {"ok": False, "error": "todos not configured"}
        # Only touch due_date when the client actually sent it; otherwise a partial
        # update (title-only) would silently clear the date (None is a valid clear).
        due_date = request.due_date if "due_date" in request.model_fields_set else _UNSET
        todo = await todo_service.update(
            todo_id,
            title=request.title,
            description=request.description,
            due_date=due_date,
        )
        if not todo:
            return {"ok": False, "error": "not found"}
        return {"ok": True, "todo": todo}

    @app.post("/todos/{todo_id}/complete")
    async def complete_todo(todo_id: int) -> dict:
        if not todo_service:
            return {"ok": False, "error": "todos not configured"}
        ok = await todo_service.complete(todo_id)
        return {"ok": ok, "error": None if ok else "not found"}

    @app.delete("/todos/{todo_id}")
    async def delete_todo(todo_id: int) -> dict:
        if not todo_service:
            return {"ok": False, "error": "todos not configured"}
        ok = await todo_service.delete(todo_id)
        return {"ok": ok, "error": None if ok else "not found"}
