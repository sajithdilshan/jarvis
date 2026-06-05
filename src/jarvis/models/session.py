"""Session, progress, and workflow I/O schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class WorkflowInput(BaseModel):
    session_id: str
    trigger: Literal["scheduled"] = "scheduled"


class ProgressEvent(BaseModel):
    session_id: str
    timestamp: datetime
    status: str
    data: dict | None = None


# --- Interactive chat workflow models ---


class ChatMessage(BaseModel):
    intent: str  # "chat", ...
    args: dict | None = None


class InteractiveWorkflowState(BaseModel):
    session_id: str
    message_count: int = 0  # tracks history size for continue-as-new
