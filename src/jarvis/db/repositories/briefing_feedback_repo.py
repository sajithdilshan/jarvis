"""Storage for briefing_log_feedback — priority-correctness ratings.

This is the verifier data source for the self-improving priority harness. On write
we snapshot the *live* briefing_log row's priority/source/category/narrative, because
briefing_log rows are upserted across polls and can drift from what the user rated.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from jarvis.db.tables import BriefingLog, BriefingLogFeedback
from jarvis.models.briefing import BriefingFeedbackRecord, BriefingFeedbackWrite


class BriefingFeedbackRepo:
    def __init__(self, sessionmaker: async_sessionmaker):
        self._sm = sessionmaker

    async def upsert_feedback(self, write: BriefingFeedbackWrite, session_id: str) -> None:
        """Record (or re-record) a rating, snapshotting the live briefing_log row.

        Idempotent on briefing_id: re-rating updates score/comment in place and
        refreshes the snapshots to whatever the entry looks like now.
        """
        async with self._sm() as session, session.begin():
            row = await session.get(BriefingLog, write.briefing_id)
            if row is None:
                raise ValueError(f"unknown briefing_id: {write.briefing_id}")

            stmt = insert(BriefingLogFeedback).values(
                briefing_id=write.briefing_id,
                score=write.score,
                comment=write.comment,
                rated_priority=row.priority,
                source=row.source,
                category=row.category,
                narrative_snapshot=row.narrative,
                session_id=session_id,
            )
            await session.execute(
                stmt.on_conflict_do_update(
                    index_elements=[BriefingLogFeedback.briefing_id],
                    set_={
                        "score": stmt.excluded.score,
                        "comment": stmt.excluded.comment,
                        "rated_priority": stmt.excluded.rated_priority,
                        "source": stmt.excluded.source,
                        "category": stmt.excluded.category,
                        "narrative_snapshot": stmt.excluded.narrative_snapshot,
                        "updated_at": func.now(),
                    },
                )
            )

    async def recent(self, limit: int = 200) -> list[BriefingFeedbackRecord]:
        """Most recent ratings (newest first) — the miner's read path."""
        async with self._sm() as session:
            result = await session.execute(
                select(BriefingLogFeedback)
                .order_by(BriefingLogFeedback.created_at.desc())
                .limit(limit)
            )
            return [self._to_record(r) for r in result.scalars().all()]

    async def for_briefing(self, briefing_id: str) -> BriefingFeedbackRecord | None:
        async with self._sm() as session:
            result = await session.execute(
                select(BriefingLogFeedback).where(
                    BriefingLogFeedback.briefing_id == briefing_id
                )
            )
            row = result.scalar_one_or_none()
            return self._to_record(row) if row else None

    @staticmethod
    def _to_record(r: BriefingLogFeedback) -> BriefingFeedbackRecord:
        return BriefingFeedbackRecord.model_validate(
            {
                "briefing_id": r.briefing_id,
                "score": r.score,
                "comment": r.comment,
                "rated_priority": r.rated_priority,
                "source": r.source,
                "category": r.category,
                "narrative_snapshot": r.narrative_snapshot,
                "created_at": r.created_at,
            }
        )
