"""BriefingService — persists the briefing stream (briefing_log)."""

from __future__ import annotations

from datetime import datetime

from jarvis.db.repositories.briefing_log_repo import BriefingLogRepo
from jarvis.models.agent_io import BriefingEntry
from jarvis.models.briefing import BriefingLogWrite


class BriefingService:
    def __init__(self, repo: BriefingLogRepo):
        self._repo = repo

    async def store_briefing_entries(self, entries: list[BriefingEntry], session_id: str) -> None:
        """Upsert briefing entries (write-once: narrative doesn't change on re-insert)."""
        rows: list[BriefingLogWrite] = []
        for entry in entries:
            ts = entry.ts
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            rows.append(
                BriefingLogWrite(
                    id=entry.id,
                    tier=entry.tier,
                    category=entry.category,
                    narrative=entry.narrative,
                    source=entry.source,
                    refs=[r.model_dump() for r in entry.refs],
                    context=entry.context if entry.context else None,
                    ts=ts,
                    priority=entry.priority,
                    permission_ref=entry.permission_ref,
                    session_id=session_id,
                )
            )
        await self._repo.upsert_many(rows)

    async def recent_unresolved(self, limit: int = 15) -> list[dict]:
        """Recent unresolved briefing entries — surfaced into the interactive chat
        context so the agent can act on alerts like overflow ('handled 5 of 6')."""
        return [r.model_dump() for r in await self._repo.recent_unresolved(limit=limit)]

    async def unresolved_full(self, limit: int = 100) -> list[dict]:
        """Full unresolved entries (all node fields) — for carry-forward into rebuilds."""
        return [r.model_dump() for r in await self._repo.unresolved_full(limit=limit)]

    async def resolve_briefing_entry(self, entry_id: str) -> None:
        """Mark a briefing entry as resolved (user dismissed it)."""
        await self._repo.mark_resolved(entry_id)

    async def count_resolved_today(self) -> int:
        return await self._repo.count_resolved_today()
