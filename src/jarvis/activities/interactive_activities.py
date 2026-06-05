"""Interactive chat activity — a single agent with lazy MCP tool loading.

MCP tools are discovered and invoked on-demand via `list_mcp_tools` and `call_mcp_tool`
rather than attaching all toolsets upfront (which would exceed token limits).
"""

from __future__ import annotations

import logging
from uuid import uuid4

from temporalio import activity

from jarvis.activities._telemetry import persist_tool_raw_data_bg, record_usage
from jarvis.agents.core.interactive.deps import InteractiveDeps
from jarvis.agents.registry import AgentRegistry
from jarvis.models.agent_io import InteractiveResponse
from jarvis.services.briefing_service import BriefingService
from jarvis.services.conversation_service import ConversationService
from jarvis.services.mcp_service import MCPService
from jarvis.services.memory_service import MemoryService
from jarvis.services.permission_service import PermissionService
from jarvis.services.progress_service import ProgressService
from jarvis.services.telemetry_service import TelemetryService
from jarvis.services.ui_service import UIService

logger = logging.getLogger(__name__)


class InteractiveActivities:
    def __init__(
        self,
        memory_service: MemoryService,
        conversation_service: ConversationService,
        telemetry_service: TelemetryService,
        progress_service: ProgressService,
        ui_service: UIService,
        permission_service: PermissionService,
        agent_registry: AgentRegistry,
        briefing_service: BriefingService,
        mcp_service: MCPService,
        interactive_model: str | None = None,
        default_model: str = "",
    ):
        self._memory = memory_service
        self._conversation = conversation_service
        self._telemetry = telemetry_service
        self._progress = progress_service
        self._ui = ui_service
        self._permissions = permission_service
        self._registry = agent_registry
        self._briefing = briefing_service
        self._mcp = mcp_service
        self._model = interactive_model or default_model

    @activity.defn
    async def run_interactive_chat(self, intent: str, args: dict | None, session_id: str) -> dict:
        """Run the interactive agent with all MCP tools directly attached.

        Streams chat tokens to the user, then records interactions and token usage
        asynchronously (best-effort, never blocks the response).
        """
        agent = self._registry.interactive_agent(self._model)
        deps = InteractiveDeps(
            memory_service=self._memory,
            progress_service=self._progress,
            permission_service=self._permissions,
            agent_registry=self._registry,
            mcp_service=self._mcp,
            session_id=session_id,
        )
        prompt = self._ui.intent_to_prompt(intent, args)

        # Prepend conversation history + recent dashboard alerts for context continuity.
        if intent == "chat":
            context_blocks = []

            history = await self._conversation.get_recent_interactions()
            if history:
                history_lines = [f"[{t['role']}]: {t['content']}" for t in history]
                context_blocks.append("## Recent conversation history\n" + "\n".join(history_lines))

            # Recent unresolved briefing entries (e.g. overflow "handled 5 of 6"),
            # so the user can act on them ("yes, do the rest") with full context.
            alerts = await self._briefing.recent_unresolved()
            if alerts:
                alert_lines = [
                    f"- [{a['tier']}/{a['source']}] {a['narrative']}"
                    + (f" (rule: {a['permission_ref']})" if a.get("permission_ref") else "")
                    for a in alerts
                ]
                context_blocks.append(
                    "## Recent dashboard alerts (unresolved)\n" + "\n".join(alert_lines)
                )

            if context_blocks:
                prompt = "\n\n".join(context_blocks) + "\n\n## Current question\n" + prompt

        # Stream the response. The reply is fully flushed to the frontend inside
        # _run_streaming before any persistence runs, so the user-perceived latency
        # is bounded by the LLM, not by DB writes.
        response = await self._run_streaming(agent, prompt, deps, session_id)

        # All persistence happens after the reply is on screen. Recording the user
        # message is deferred here (rather than pre-agent) so it never delays
        # time-to-first-token.
        if intent == "chat":
            user_message = args.get("message", "") if args else ""
            await self._conversation.record_interaction(session_id, "user", user_message)
            if response.chat_reply:
                await self._conversation.record_interaction(
                    session_id, "assistant", response.chat_reply
                )

        return response.model_dump()

    async def _run_streaming(
        self, agent, prompt: str, deps: InteractiveDeps, session_id: str
    ) -> InteractiveResponse:
        """Stream chat_reply tokens and record usage."""
        msg_id = uuid4().hex
        sent = 0
        response: InteractiveResponse | None = None

        async with agent:
            async with agent.run_stream(prompt, deps=deps) as stream:
                async for partial in stream.stream_output(debounce_by=0.05):
                    reply = getattr(partial, "chat_reply", None) or ""
                    if len(reply) > sent:
                        await self._ui.stream_chat_token(session_id, msg_id, reply[sent:])
                        sent = len(reply)
                response = await stream.get_output()

                # Flush any remaining text FIRST so the user sees the full reply
                # immediately; token-usage + raw-data persistence happen after.
                final_reply = response.chat_reply or ""
                if len(final_reply) > sent:
                    await self._ui.stream_chat_token(session_id, msg_id, final_reply[sent:])

                await record_usage(
                    self._telemetry,
                    session_id=session_id,
                    trigger="user_request",
                    activity="run_interactive_chat",
                    agent="interactive",
                    model=self._model,
                    usage=stream.usage(),
                )
                persist_tool_raw_data_bg(self._memory, stream, "interactive")

        return response
