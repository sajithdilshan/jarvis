"""PermissionService — CRUD for standing automation rules.

Permissions are the trust layer: they define what Jarvis can do autonomously.
All management (create/update/revoke) happens via the agent's tool calls,
triggered by user chat messages.
"""

from __future__ import annotations

from uuid import uuid4

from jarvis.db.repositories.permission_repo import _UNSET, PermissionRepo
from jarvis.models.permission import PermissionCreate, PermissionExecutionAuditRow


class PermissionService:
    def __init__(self, repo: PermissionRepo):
        self._repo = repo

    async def create(
        self,
        description: str,
        source: str | None,
        constraints: dict,
        allowed_actions: list[str],
        created_via: str | None = None,
        max_matches: int | None = None,
    ) -> dict:
        """Create a new standing permission. Returns the full record.

        max_matches: per-rule circuit-breaker cap — None=default, 0=unlimited, N=cap.
        """
        perm_id = f"perm-{uuid4().hex[:12]}"
        record = PermissionCreate(
            id=perm_id,
            description=description,
            source=source,
            constraints=constraints,
            allowed_actions=allowed_actions,
            created_via=created_via,
            max_matches=max_matches,
        )
        await self._repo.insert(record)
        return record.model_dump() | {"active": True}

    async def update(
        self,
        permission_id: str,
        description: str | None = None,
        source: str | None = None,
        constraints: dict | None = None,
        allowed_actions: list[str] | None = None,
        max_matches: int | None | object = _UNSET,
    ) -> dict | None:
        """Update an existing permission. Returns updated record or None if not found.

        max_matches uses a sentinel since None is a valid new value (= use default).
        """
        record = await self._repo.apply_partial_update(
            permission_id,
            description=description,
            source=source,
            constraints=constraints,
            allowed_actions=allowed_actions,
            max_matches=max_matches,
        )
        return record.model_dump() if record else None

    async def revoke(self, permission_id: str) -> bool:
        """Deactivate a permission. Returns False if not found / already inactive."""
        return await self._repo.set_active(permission_id, False)

    async def reactivate(self, permission_id: str) -> bool:
        """Re-enable a previously revoked permission."""
        return await self._repo.set_active(permission_id, True)

    async def delete(self, permission_id: str) -> bool:
        """Permanently remove a permission. Returns False if not found."""
        return await self._repo.delete(permission_id)

    async def record_executions(self, rows: list[dict]) -> None:
        """Append per-item execution outcomes to executed_permissions_audit."""
        await self._repo.record_executions(
            [PermissionExecutionAuditRow.model_validate(row) for row in rows]
        )

    async def list_active(self) -> list[dict]:
        return [r.model_dump() for r in await self._repo.list_active()]

    async def list_all(self) -> list[dict]:
        return [r.model_dump() for r in await self._repo.list_all()]

    async def get(self, permission_id: str) -> dict | None:
        record = await self._repo.get(permission_id)
        return record.model_dump() if record else None

    async def find_by_description(self, query: str) -> list[dict]:
        """Fuzzy search permissions by description (for revoke-by-name flows)."""
        return [r.model_dump() for r in await self._repo.find_by_description(query)]
