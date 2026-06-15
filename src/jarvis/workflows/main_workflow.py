"""Main agent workflow.

Scheduled fan-out to source agents -> main-agent synthesize -> UI patch -> save.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from jarvis.models.session import WorkflowInput
    from jarvis.workflows.activity_options import (
        EXECUTE_PERMISSIONS,
        GET_POLL_WATERMARK,
        LIST_REGISTERED_AGENTS,
        PUBLISH_BRIEFING,
        REPORT_SOURCE_FAILURES,
        RUN_MAIN_AGENT_SYNTHESIZE,
        RUN_SUB_AGENT,
        SET_POLL_WATERMARK,
        agent_activity,
        publish_activity,
        quick_activity,
        short_activity,
        sub_agent_activity,
    )


def _window_phrase(last) -> str:
    """The 'since' clause for the sub-agent task, with all formats each source needs.

    ``last`` is an ISO-8601 string (the poll watermark) or falsy on the first run.
    Returns a human phrase that bundles
    every representation so each agent's prompt can pick the one its API wants:
      - ISO-8601 (GitHub `since=`/`updated:>=`, Slack client-side compare)
      - epoch seconds (Gmail `after:`)
      - "yyyy-MM-dd HH:mm" UTC (Atlassian JQL/CQL date literals — reject ISO 'T'/offset)
    Pure formatting of an already-fixed timestamp, so it stays Temporal-deterministic
    (no wall-clock read here)."""
    if not last:
        return "from the last 24 hours"
    dt = last if isinstance(last, datetime) else datetime.fromisoformat(last)
    iso = dt.isoformat()
    epoch = int(dt.timestamp())
    jql = dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")
    return f'since {iso} (epoch seconds: {epoch}; JQL/CQL UTC datetime: "{jql}")'


def _short_error(exc: BaseException) -> str:
    """A compact, user-facing reason for a failed source (no stack traces)."""
    msg = str(exc) or type(exc).__name__
    # Temporal wraps activity failures; the tail usually holds the real cause.
    msg = msg.strip().splitlines()[-1] if msg else type(exc).__name__
    return msg[:200]


@workflow.defn
class MainAgentWorkflow:
    @workflow.run
    async def run(self, wf_input: WorkflowInput) -> dict:
        return await self._scheduled_run(wf_input)

    async def _scheduled_run(self, wf_input: WorkflowInput) -> dict:
        sid = wf_input.session_id
        # Stamp the window's upper bound NOW (deterministic — workflow.now(), never
        # datetime.now()). We persist this as the new watermark only if the run finishes
        # with no source failures, so the next 'since' picks up exactly where a clean run
        # left off and a failed run re-covers the same window.
        run_started_at = workflow.now().isoformat()

        agent_names: list[str] = await workflow.execute_activity(
            LIST_REGISTERED_AGENTS,
            **short_activity(),
        )

        # 'since' = the last *successful* poll's start time (None on first run -> 24h).
        last = await workflow.execute_activity(
            GET_POLL_WATERMARK,
            **short_activity(),
        )
        # Bundle every timestamp format sources need (ISO / epoch / JQL-CQL datetime) so
        # each agent's prompt picks the right one instead of doing error-prone conversion.
        since = _window_phrase(last)
        tasks = [
            workflow.execute_activity(
                RUN_SUB_AGENT,
                args=[name, f"Check for new data {since}", sid],
                **sub_agent_activity(),
            )
            for name in agent_names
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        agent_results = {}
        failures = {}
        for name, result in zip(agent_names, results):
            if isinstance(result, Exception):
                failures[name] = _short_error(result)
            else:
                agent_results[name] = result

        # Surface any failed sources as error cards (deterministic patch, no LLM).
        if failures:
            await workflow.execute_activity(
                REPORT_SOURCE_FAILURES,
                args=[sid, failures, "rebuild"],
                **quick_activity(),
            )

        if not agent_results:
            # No data this poll. Advance the watermark only if nothing failed — an
            # all-failed poll must re-cover this window next time.
            if not failures:
                await self._advance_watermark(run_started_at)
            return {
                "session_id": sid,
                "agents": [],
                "synthesized": False,
                "advanced": not failures,
            }

        # Phase 3: Execute standing permissions BEFORE synthesis. This acts on items
        # autonomously (archive, mark_read, etc.) and produces "did" entries. Runs first
        # so synthesis knows which items were already handled and doesn't flag working
        # permissions as broken.
        perm_result = await workflow.execute_activity(
            EXECUTE_PERMISSIONS,
            args=[agent_results, sid],
            **agent_activity(minutes=2),
        )

        # Main agent synthesizes the aggregated data; returns briefing + memory. It also
        # receives the permission execution result so it knows what was acted on.
        response = await workflow.execute_activity(
            RUN_MAIN_AGENT_SYNTHESIZE,
            args=[agent_results, perm_result, sid],
            **agent_activity(),
        )

        # Merge "did" entries and overflow alerts into the briefing stream.
        all_briefing = (
            perm_result.get("did_entries", [])
            + perm_result.get("overflow_alerts", [])
            + response.get("briefing", [])
        )

        # Deterministic patch: convert briefing entries to ViewModel ops — no LLM.
        # (Memory is persisted by the synthesize agent itself during its run.)
        await workflow.execute_activity(
            PUBLISH_BRIEFING,
            args=[all_briefing, sid, "rebuild"],
            **publish_activity(),
        )

        # Clean run: advance the watermark to this run's start. On a partial-failure run
        # we deliberately leave it, so the failed sources' window is retried next poll.
        if not failures:
            await self._advance_watermark(run_started_at)
        return {
            "session_id": sid,
            "agents": list(agent_results),
            "synthesized": True,
            "advanced": not failures,
        }

    async def _advance_watermark(self, run_started_at: str) -> None:
        """Persist this run's start time as the last successful poll watermark."""
        await workflow.execute_activity(
            SET_POLL_WATERMARK,
            args=[run_started_at],
            **short_activity(),
        )
