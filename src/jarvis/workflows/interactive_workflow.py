"""Long-lived interactive chat workflow.

Stays alive for the duration of a browser session, blocking on signals. Each user
message arrives as a signal, triggering the interactive agent activity. This eliminates
per-message workflow scheduling overhead. Uses continue-as-new to bound history growth.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from jarvis.models.session import ChatMessage, InteractiveWorkflowState
    from jarvis.workflows.activity_options import (
        RUN_INTERACTIVE_CHAT,
        agent_activity,
    )

# Continue-as-new after this many messages to keep workflow history bounded.
_MAX_MESSAGES_BEFORE_CONTINUE = 50

# If no message arrives within this window, the workflow completes (session expired).
_IDLE_TIMEOUT = timedelta(hours=2)


@workflow.defn
class InteractiveChatWorkflow:
    def __init__(self) -> None:
        self._pending: list[ChatMessage] = []
        self._message_count: int = 0

    @workflow.run
    async def run(self, state: InteractiveWorkflowState) -> dict:
        self._message_count = state.message_count

        while True:
            # Wait for a signal or idle timeout.
            try:
                await workflow.wait_condition(
                    lambda: len(self._pending) > 0,
                    timeout=_IDLE_TIMEOUT,
                )
            except asyncio.TimeoutError:
                return {"session_id": state.session_id, "reason": "idle_timeout"}

            # Drain all pending messages (typically one, but handle bursts).
            while self._pending:
                msg = self._pending.pop(0)
                self._message_count += 1

                # Run the interactive agent activity. The interactive agent persists
                # its own conversation turns + memory (via its store_memory tool); it
                # emits no briefing/raw-data, so there's no post-run bookkeeping here.
                await workflow.execute_activity(
                    RUN_INTERACTIVE_CHAT,
                    args=[msg.intent, msg.args, state.session_id],
                    **agent_activity(),
                )

            # Continue-as-new to bound history growth.
            if self._message_count >= _MAX_MESSAGES_BEFORE_CONTINUE:
                workflow.continue_as_new(
                    InteractiveWorkflowState(
                        session_id=state.session_id,
                        message_count=0,
                    )
                )

    @workflow.signal
    async def chat_message(self, msg: ChatMessage) -> None:
        self._pending.append(msg)
