"""Storage for briefing_log — the persisted briefing stream."""

from __future__ import annotations

from sqlalchemy import case, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from jarvis.db.tables import BriefingLog
from jarvis.models.briefing import BriefingAlertSummary, BriefingLogRecord, BriefingLogWrite


def _upsert_stmt(values: dict):
    """Write-once narrative; on conflict refresh tier/category/refs/priority/permission_ref.

    For 'ask' entries only, also clear resolved_at: re-emitting an 'ask' under an existing
    id means it needs the user again (e.g. a rule overflows on a later poll after the
    previous alert was dismissed), so it should resurface. 'noticed' entries keep their
    resolved_at — a dismissed observation the agent re-emits next poll stays dismissed,
    not resurrected. ('did' ids are unique per run, so they never hit this path.)
    """
    stmt = insert(BriefingLog).values(**values)
    return stmt.on_conflict_do_update(
        index_elements=[BriefingLog.id],
        set_={
            "tier": stmt.excluded.tier,
            "category": stmt.excluded.category,
            "refs": stmt.excluded.refs,
            "priority": stmt.excluded.priority,
            "permission_ref": stmt.excluded.permission_ref,
            "resolved_at": case(
                (stmt.excluded.category == "ask", None),
                else_=BriefingLog.resolved_at,
            ),
        },
    )


class BriefingLogRepo:
    def __init__(self, sessionmaker: async_sessionmaker):
        self._sm = sessionmaker

    async def upsert_many(self, rows: list[BriefingLogWrite]) -> None:
        """Upsert a batch of briefing entries in one transaction. Each dict holds the
        BriefingLog column values (id, tier, narrative, source, refs, context, ts,
        priority, permission_ref, session_id)."""
        if not rows:
            return
        async with self._sm() as session, session.begin():
            for row in rows:
                await session.execute(_upsert_stmt(row.model_dump()))

    async def recent_unresolved(self, limit: int = 15) -> list[BriefingAlertSummary]:
        """Most recent unresolved entries (newest first) — for chat context.

        Returns lightweight dicts: narrative, tier, source, permission_ref, ts.
        """
        async with self._sm() as session:
            result = await session.execute(
                select(
                    BriefingLog.narrative,
                    BriefingLog.tier,
                    BriefingLog.source,
                    BriefingLog.permission_ref,
                    BriefingLog.ts,
                )
                .where(BriefingLog.resolved_at.is_(None))
                .order_by(BriefingLog.ts.desc())
                .limit(limit)
            )
            return [BriefingAlertSummary.model_validate(dict(r._mapping)) for r in result]

    async def unresolved_full(self, limit: int = 100) -> list[BriefingLogRecord]:
        """All columns for unresolved entries (newest first) — enough to rebuild full
        ViewModel nodes for carry-forward. Heavier than recent_unresolved, which returns
        only the lightweight fields the chat context needs."""
        async with self._sm() as session:
            result = await session.execute(
                select(BriefingLog)
                .where(BriefingLog.resolved_at.is_(None))
                .order_by(BriefingLog.ts.desc())
                .limit(limit)
            )
            return [
                BriefingLogRecord.model_validate(
                    {
                        "id": r.id,
                        "tier": r.tier,
                        "category": r.category,
                        "narrative": r.narrative,
                        "source": r.source,
                        "refs": r.refs or [],
                        "context": r.context,
                        "ts": r.ts.isoformat(),
                        "priority": r.priority,
                        "permission_ref": r.permission_ref,
                    }
                )
                for r in result.scalars().all()
            ]

    async def mark_resolved(self, entry_id: str, *, only_unresolved: bool = False) -> None:
        stmt = update(BriefingLog).where(BriefingLog.id == entry_id)
        if only_unresolved:
            stmt = stmt.where(BriefingLog.resolved_at.is_(None))
        async with self._sm() as session, session.begin():
            await session.execute(stmt.values(resolved_at=func.now()))

    async def count_resolved_today(self) -> int:
        async with self._sm() as session:
            count = await session.scalar(
                select(func.count())
                .select_from(BriefingLog)
                .where(
                    BriefingLog.resolved_at.isnot(None),
                    BriefingLog.resolved_at >= func.current_date(),
                )
            )
        return count or 0
