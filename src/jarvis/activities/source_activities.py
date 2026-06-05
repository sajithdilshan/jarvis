"""Source-agent activities — list agents, poll history, run a single sub-agent.

The scheduled flow's first stage: discover registered source agents and run each
(gmail, slack, ...) with its MCP tools to collect raw data.
"""

from __future__ import annotations

import logging

from temporalio import activity

from jarvis.activities._telemetry import persist_tool_raw_data_bg, record_usage
from jarvis.agents.registry import AgentRegistry
from jarvis.services.memory_service import MemoryService
from jarvis.services.poll_watermark_service import PollWatermarkService
from jarvis.services.progress_service import ProgressService
from jarvis.services.telemetry_service import TelemetryService

logger = logging.getLogger(__name__)


class SourceActivities:
    def __init__(
        self,
        memory_service: MemoryService,
        progress_service: ProgressService,
        agent_registry: AgentRegistry,
        poll_watermark_service: PollWatermarkService,
        telemetry_service: TelemetryService,
    ):
        self._memory = memory_service
        self._progress = progress_service
        self._registry = agent_registry
        self._watermark = poll_watermark_service
        self._telemetry = telemetry_service

    @activity.defn
    async def list_registered_agents(self) -> list[str]:
        return self._registry.list_agents()

    @activity.defn
    async def get_poll_watermark(self) -> str | None:
        """Start time of the last successful scheduled poll (None on first run)."""
        return await self._watermark.get_last_successful()

    @activity.defn
    async def set_poll_watermark(self, run_started_at: str) -> None:
        """Advance the watermark to this run's start (called only on a clean run)."""
        await self._watermark.mark_successful(run_started_at)

    @activity.defn
    async def run_sub_agent(self, agent_name: str, task: str, session_id: str) -> dict:
        """Run a source agent (gmail, ...) with its MCP tools and return its summary."""
        await self._progress.publish(session_id, f"{agent_name}_checking")
        agent = self._registry.get_agent(agent_name)
        async with agent:  # opens MCP toolset connections
            result = await agent.run(task)
        await record_usage(
            self._telemetry,
            session_id=session_id,
            trigger="scheduled",
            activity="run_sub_agent",
            agent=agent_name,
            model=self._registry.model_for(agent_name),
            usage=result.usage,
        )
        persist_tool_raw_data_bg(self._memory, result, agent_name)
        data = result.output.model_dump()
        await self._progress.publish(session_id, f"{agent_name}_complete", data)
        return data
