"""Synthesis activity.

The scheduled flow's reasoning stage: run the main agent over aggregated sub-agent data.
The agent persists memory itself during the run via its `store_memory` tool. The dashboard
ViewModel is persisted separately (see BriefingActivities), so what the UI shows is
decoupled from the agent's memory.
"""

from __future__ import annotations

import json
import logging

from temporalio import activity

from jarvis.activities._telemetry import persist_tool_raw_data_bg, record_usage
from jarvis.agents.core.synthesize import SynthesizeAgentDeps
from jarvis.agents.registry import AgentRegistry
from jarvis.models.agent_io import SynthesizeResponse
from jarvis.services.memory_service import MemoryService
from jarvis.services.permission_service import PermissionService
from jarvis.services.progress_service import ProgressService
from jarvis.services.telemetry_service import TelemetryService

logger = logging.getLogger(__name__)


class SynthesisActivities:
    def __init__(
        self,
        memory_service: MemoryService,
        progress_service: ProgressService,
        agent_registry: AgentRegistry,
        telemetry_service: TelemetryService,
        permission_service: PermissionService,
        default_model: str,
    ):
        self._memory = memory_service
        self._progress = progress_service
        self._registry = agent_registry
        self._telemetry = telemetry_service
        self._permissions = permission_service
        self._default_model = default_model

    @activity.defn
    async def run_main_agent_synthesize(self, agent_results: dict, session_id: str) -> dict:
        """Run the main agent over aggregated sub-agent data; persist raw tool data."""
        agent = self._registry.synthesize_agent()
        deps = SynthesizeAgentDeps(
            memory_service=self._memory,
            permission_service=self._permissions,
            session_id=session_id,
        )
        await self._progress.publish(session_id, "synthesizing")
        context = (
            "Synthesize the following data from sub-agents and decide what is "
            "important. Store key items to memory.\n\n"
            f"{json.dumps(agent_results, indent=2, default=str)}"
        )
        result = await agent.run(context, deps=deps)
        response: SynthesizeResponse = result.output
        await record_usage(
            self._telemetry,
            session_id=session_id,
            trigger="scheduled",
            activity="run_main_agent_synthesize",
            agent="synthesize",
            model=self._default_model,
            usage=result.usage,
        )
        persist_tool_raw_data_bg(self._memory, result, "synthesize")

        await self._progress.publish(session_id, "synthesize_complete")
        return response.model_dump()
