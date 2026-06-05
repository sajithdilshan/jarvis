"""Permission-execution activities."""

from __future__ import annotations

from temporalio import activity

from jarvis.services.permission_execution_service import PermissionExecutionService


class PermissionActivities:
    def __init__(self, execution_service: PermissionExecutionService):
        self._execution = execution_service

    @activity.defn
    async def execute_permissions(self, agent_results: dict, session_id: str) -> dict:
        """Evaluate permissions against sub-agent results and execute matched actions.

        For each source's items:
        1. Load active permissions
        2. Match items against permission constraints (deterministic, no LLM)
        3. Batch all matched items for the source into ONE agent run that calls the
           stored MCP tool names directly (no re-interpretation)
        4. Return "did" BriefingEntries for confirmed actions + "noticed" entries for
           skips/failures + circuit-breaker overflow alerts

        Returns: {"did_entries": [...], "overflow_alerts": [...]}
        """
        return await self._execution.execute(agent_results, session_id)
