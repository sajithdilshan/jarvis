"""Storage for permissions + executed_permissions_audit."""

from __future__ import annotations

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from jarvis.db.tables import ExecutedPermissionAudit, Permission
from jarvis.models.permission import (
    PermissionCreate,
    PermissionExecutionAuditRow,
    PermissionRecord,
    PermissionUpdate,
    permission_record_from_row,
)

# Sentinel: "argument not supplied" — distinct from None, which is a valid value for
# max_matches (None means "use the engine default").
_UNSET = object()


class PermissionRepo:
    def __init__(self, sessionmaker: async_sessionmaker):
        self._sm = sessionmaker

    async def insert(self, record: PermissionCreate) -> None:
        async with self._sm() as session, session.begin():
            await session.execute(
                insert(Permission).values(
                    id=record.id,
                    description=record.description,
                    source=record.source,
                    constraints=record.constraints,
                    allowed_actions=record.allowed_actions,
                    created_via=record.created_via,
                    max_matches=record.max_matches,
                )
            )

    async def apply_partial_update(
        self,
        permission_id: str,
        *,
        description: str | None,
        source: str | None,
        constraints: dict | None,
        allowed_actions: list[str] | None,
        max_matches: int | None | object = _UNSET,
    ) -> PermissionRecord | None:
        """Read-modify-write in one transaction: fields left None keep their current
        value. Returns the merged record, or None if the permission doesn't exist.

        max_matches uses a sentinel (_UNSET) since None is a valid new value.
        """
        async with self._sm() as session, session.begin():
            row = await session.get(Permission, permission_id)
            if not row:
                return None
            new = PermissionUpdate(
                description=description if description is not None else row.description,
                source=source if source is not None else row.source,
                constraints=constraints if constraints is not None else row.constraints,
                allowed_actions=allowed_actions
                if allowed_actions is not None
                else list(row.allowed_actions or []),
                max_matches=row.max_matches if max_matches is _UNSET else max_matches,
            )
            active = row.active
            await session.execute(
                update(Permission).where(Permission.id == permission_id).values(**new.model_dump())
            )
        return PermissionRecord(id=permission_id, active=active, **new.model_dump())

    async def set_active(self, permission_id: str, active: bool) -> bool:
        """Flip active state only when transitioning; returns True if a row changed."""
        async with self._sm() as session, session.begin():
            result = await session.execute(
                update(Permission)
                .where(Permission.id == permission_id, Permission.active == (not active))
                .values(active=active)
            )
        return result.rowcount == 1

    async def delete(self, permission_id: str) -> bool:
        """Hard-delete a permission; returns True if a row was removed."""
        async with self._sm() as session, session.begin():
            result = await session.execute(delete(Permission).where(Permission.id == permission_id))
        return result.rowcount == 1

    async def get(self, permission_id: str) -> PermissionRecord | None:
        async with self._sm() as session:
            row = await session.get(Permission, permission_id)
        return permission_record_from_row(row) if row else None

    async def _list(self, stmt) -> list[PermissionRecord]:
        async with self._sm() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return [permission_record_from_row(r) for r in rows]

    async def list_active(self) -> list[PermissionRecord]:
        return await self._list(
            select(Permission)
            .where(Permission.active.is_(True))
            .order_by(Permission.created_at.desc())
        )

    async def list_all(self) -> list[PermissionRecord]:
        return await self._list(
            select(Permission).order_by(Permission.active.desc(), Permission.created_at.desc())
        )

    async def find_by_description(self, query: str) -> list[PermissionRecord]:
        return await self._list(
            select(Permission)
            .where(
                Permission.active.is_(True),
                Permission.description.ilike(f"%{query}%"),
            )
            .order_by(Permission.created_at.desc())
        )

    async def record_executions(self, rows: list[PermissionExecutionAuditRow]) -> None:
        if not rows:
            return
        async with self._sm() as session, session.begin():
            await session.execute(
                insert(ExecutedPermissionAudit),
                [
                    {
                        "permission_id": r.permission_id,
                        "permission_desc": r.permission_desc,
                        "session_id": r.session_id,
                        "source": r.source,
                        "item_id": r.item_id,
                        "tool": r.tool,
                        "status": r.status,
                        "detail": r.detail,
                    }
                    for r in rows
                ],
            )
