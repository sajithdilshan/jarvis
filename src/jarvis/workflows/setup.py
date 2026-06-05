"""Create/ensure the periodic poll schedule on startup."""

from __future__ import annotations

import logging

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleOverlapPolicy,
    SchedulePolicy,
    ScheduleSpec,
    ScheduleUpdate,
)

from jarvis.models.session import WorkflowInput
from jarvis.workflows.main_workflow import MainAgentWorkflow

logger = logging.getLogger(__name__)

SCHEDULE_ID = "jarvis-periodic-poll"


async def ensure_schedule(
    client: Client,
    task_queue: str,
    cron: str,
    timezone: str = "Europe/Berlin",
    enabled: bool = True,
) -> None:
    """Create/update the poll schedule, or delete it if disabled.

    Idempotent on every boot: applies the configured cron (and SKIP overlap) to an
    existing schedule, and tears it down when ``enabled`` is False so a previously-created
    schedule stops firing.
    """
    if not enabled:
        try:
            await client.get_schedule_handle(SCHEDULE_ID).delete()
            logger.info("Schedule '%s' disabled (deleted)", SCHEDULE_ID)
        except Exception as exc:  # not found / already gone
            logger.info("Schedule '%s' not active (%s)", SCHEDULE_ID, exc)
        return

    action = ScheduleActionStartWorkflow(
        MainAgentWorkflow.run,
        WorkflowInput(session_id="default", trigger="scheduled"),
        id="jarvis-scheduled",
        task_queue=task_queue,
    )
    schedule = Schedule(
        action=action,
        spec=ScheduleSpec(
            cron_expressions=[cron],
            time_zone_name=timezone,
        ),
        policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
    )
    try:
        await client.create_schedule(SCHEDULE_ID, schedule)
        logger.info("Created schedule '%s' (cron=%s, tz=%s)", SCHEDULE_ID, cron, timezone)
        return
    except Exception as exc:
        logger.info("Schedule '%s' exists; updating (%s)", SCHEDULE_ID, exc)

    async def _update_spec(inp):
        sched = inp.description.schedule
        sched.policy.overlap = ScheduleOverlapPolicy.SKIP
        sched.spec.cron_expressions = [cron]
        sched.spec.time_zone_name = timezone
        sched.spec.intervals = []
        return ScheduleUpdate(schedule=sched)

    try:
        await client.get_schedule_handle(SCHEDULE_ID).update(_update_spec)
    except Exception as exc:
        logger.warning("Could not update schedule '%s': %s", SCHEDULE_ID, exc)
