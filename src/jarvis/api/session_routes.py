"""Session and agent-invocation routes."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from pydantic import BaseModel, Field
from temporalio.client import Client, WorkflowExecutionStatus

from jarvis.models.session import ChatMessage, InteractiveWorkflowState
from jarvis.services.conversation_service import ConversationService
from jarvis.workflows.interactive_workflow import InteractiveChatWorkflow

logger = logging.getLogger(__name__)

INTERACTIVE_WORKFLOW_ID = "jarvis-interactive"
INTERACTIVE_SESSION_ID = "interactive"


class UserInvokeRequest(BaseModel):
    session_id: str
    intent: str
    args: dict = Field(default_factory=dict)


def register_session_routes(
    app: FastAPI,
    *,
    temporal_client: Client,
    task_queue: str,
    conversation_service: ConversationService,
) -> None:
    async def ensure_interactive_workflow() -> None:
        handle = temporal_client.get_workflow_handle(INTERACTIVE_WORKFLOW_ID)
        try:
            desc = await handle.describe()
            if desc.status == WorkflowExecutionStatus.RUNNING:
                return
        except Exception:
            pass
        try:
            await temporal_client.start_workflow(
                InteractiveChatWorkflow.run,
                InteractiveWorkflowState(session_id=INTERACTIVE_SESSION_ID),
                id=INTERACTIVE_WORKFLOW_ID,
                task_queue=task_queue,
            )
        except Exception as exc:
            logger.debug("interactive workflow start race: %s", exc)

    @app.post("/agent/invoke")
    async def invoke_agent(request: UserInvokeRequest) -> dict:
        """A click or chat message — signals the single interactive workflow."""
        await ensure_interactive_workflow()
        handle = temporal_client.get_workflow_handle(INTERACTIVE_WORKFLOW_ID)
        await handle.signal(
            InteractiveChatWorkflow.chat_message,
            ChatMessage(intent=request.intent, args=request.args),
        )
        return {"workflow_id": INTERACTIVE_WORKFLOW_ID}

    @app.get("/session")
    async def get_session() -> dict:
        """Return the single shared session, creating the workflow if needed."""
        await ensure_interactive_workflow()
        return {"session_id": INTERACTIVE_SESSION_ID}

    @app.post("/session/resume")
    async def resume_session(request: dict) -> dict:
        """Legacy resume — just ensures the workflow is alive."""
        await ensure_interactive_workflow()
        return {"session_id": INTERACTIVE_SESSION_ID}

    @app.get("/chat-history")
    async def chat_history(before_id: int | None = None) -> list[dict]:
        """Chat thread page (10 messages). Omit ``before_id`` for the latest;
        pass it to page backwards through older history."""
        return await conversation_service.get_recent_messages(limit=10, before_id=before_id)
