"""Typed contracts for persisted briefing rows."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from jarvis.models.agent_io import Ref


class BriefingLogWrite(BaseModel):
    id: str
    tier: Literal["noticed", "did"] = "noticed"
    category: Literal["did", "ask", "noticed"] = "noticed"
    narrative: str
    source: str
    refs: list[dict[str, Any]] = Field(default_factory=list)
    context: dict[str, Any] | None = None
    ts: datetime
    priority: Literal["low", "normal", "high"] = "normal"
    permission_ref: str | None = None
    session_id: str


class BriefingLogRecord(BaseModel):
    id: str
    tier: Literal["noticed", "did"] = "noticed"
    category: Literal["did", "ask", "noticed"] = "noticed"
    narrative: str
    source: str
    refs: list[Ref] = Field(default_factory=list)
    context: dict[str, Any] | None = None
    ts: str
    priority: Literal["low", "normal", "high"] = "normal"
    permission_ref: str | None = None


class BriefingAlertSummary(BaseModel):
    narrative: str
    tier: str
    source: str
    permission_ref: str | None = None
    ts: datetime
