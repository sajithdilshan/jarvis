"""Dashboard/briefing activities — persist BriefingEntry rows, then nudge the UI.

The feed is never streamed: entries are written to ``briefing_log`` (the source of
truth) and a tiny ``feed_refresh`` ping tells listening tabs to refetch ``/view-model``.
Kept LLM-free so the UI stays decoupled from the agent's reasoning.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from temporalio import activity

from jarvis.models.agent_io import BriefingEntry
from jarvis.services.briefing_service import BriefingService
from jarvis.services.ui_service import DEFAULT_CHANNEL, UIService

logger = logging.getLogger(__name__)


class BriefingActivities:
    def __init__(self, briefing_service: BriefingService, ui_service: UIService):
        self._briefing = briefing_service
        self._ui = ui_service

    @activity.defn(name="publish_briefing")
    async def publish_briefing(self, briefing_data: list[dict], session_id: str, mode: str) -> int:
        """Persist briefing entries, then nudge listening tabs to refetch the feed.

        No carry-forward needed: /view-model rebuilds from ALL unresolved rows, so
        entries the agent didn't re-emit this run remain visible automatically.
        mode=='patch' (user action) refreshes only this session; otherwise (scheduled
        'rebuild') the shared 'default' channel reaches every tab. Returns the count
        persisted (debugging/observability — the feed is read back via /view-model).
        """
        channel = session_id if mode == "patch" else DEFAULT_CHANNEL
        entries = [BriefingEntry.model_validate(e) for e in briefing_data]
        await self._briefing.store_briefing_entries(entries, session_id)
        await self._ui.publish_feed_refresh(channel)
        return len(entries)

    @activity.defn
    async def report_source_failures(self, session_id: str, failures: dict, mode: str) -> None:
        """Persist failed sources as briefing entries so they survive reload + rebuild.

        Stable id per source (``error-<source>``) so a later successful run can resolve
        or replace it. Written to briefing_log like any other entry; the feed_refresh is
        emitted by the subsequent publish_briefing (or here if it's the only output)."""
        now = datetime.now(timezone.utc).isoformat()
        entries = [
            BriefingEntry(
                id=f"error-{source}",
                tier="noticed",
                category="ask",
                narrative=f"Failed to check {source}: {reason}",
                source=source,
                ts=now,
                priority="normal",
            )
            for source, reason in failures.items()
        ]
        if not entries:
            return
        await self._briefing.store_briefing_entries(entries, session_id)
        channel = session_id if mode == "patch" else DEFAULT_CHANNEL
        await self._ui.publish_feed_refresh(channel)
