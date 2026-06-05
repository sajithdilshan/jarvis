"""PollWatermarkService — reads/advances the scheduled-poll 'since' watermark.

The watermark is the start time of the last poll that finished with no source
failures. The scheduled workflow reads it to scope each run and only advances it on a
clean run, so a failed source makes the next run re-cover the same window.
"""

from __future__ import annotations

from datetime import datetime

from jarvis.db.repositories.poll_watermark_repo import PollWatermarkRepo


class PollWatermarkService:
    def __init__(self, repo: PollWatermarkRepo):
        self._repo = repo

    async def get_last_successful(self) -> str | None:
        """ISO timestamp of the last successful poll's start, or None on first run."""
        ts = await self._repo.get()
        return ts.isoformat() if ts else None

    async def mark_successful(self, run_started_at: str) -> None:
        """Advance the watermark to this run's start time (called only on a clean run)."""
        await self._repo.set(datetime.fromisoformat(run_started_at))
