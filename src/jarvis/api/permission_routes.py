"""Permission management routes."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from jarvis.services.permission_service import PermissionService


def register_permission_routes(
    app: FastAPI, *, permission_service: PermissionService | None
) -> None:
    @app.get("/permissions")
    async def get_permissions() -> JSONResponse:
        """List all permissions for the settings popup."""
        if not permission_service:
            return JSONResponse([])
        return JSONResponse(await permission_service.list_all())

    @app.post("/permissions/{permission_id}/toggle")
    async def toggle_permission(permission_id: str) -> dict:
        """Toggle a permission active/inactive from the settings popup."""
        if not permission_service:
            return {"ok": False, "error": "permissions not configured"}
        perm = await permission_service.get(permission_id)
        if not perm:
            return {"ok": False, "error": "not found"}
        if perm["active"]:
            await permission_service.revoke(permission_id)
        else:
            await permission_service.reactivate(permission_id)
        return {"ok": True}

    @app.delete("/permissions/{permission_id}")
    async def delete_permission(permission_id: str) -> dict:
        """Permanently delete a permission from the settings popup."""
        if not permission_service:
            return {"ok": False, "error": "permissions not configured"}
        deleted = await permission_service.delete(permission_id)
        return {"ok": deleted, "error": None if deleted else "not found"}
