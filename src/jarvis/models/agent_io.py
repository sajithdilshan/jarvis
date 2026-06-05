"""Main agent output schema (shared across the app)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Ref(BaseModel):
    label: str  # "Open PR", "View email", "Go to thread"
    url: str  # direct link — browser opens immediately


class BriefingEntry(BaseModel):
    id: str  # stable across polls for the same item
    tier: Literal["noticed", "did"] = "noticed"
    # UI grouping, independent of tier: "did" = action taken, "ask" = needs a decision
    # (e.g. overflow), "noticed" = observation. Drives which sidebar section it lands in.
    category: Literal["did", "ask", "noticed"] = "noticed"
    narrative: str  # one or two natural sentences
    context: dict[str, Any] | None = None  # expandable detail
    source: str  # "github", "gmail", "slack", "calendar"
    refs: list[Ref] = Field(default_factory=list)  # direct source links
    ts: str  # ISO-8601 timestamp of the underlying event
    priority: Literal["low", "normal", "high"] = "normal"
    permission_ref: str | None = None  # for "did" tier: which permission was used


class ActionResult(BaseModel):
    """Per-item outcome of a batched permission-action run."""

    item_id: str
    tool: str  # the MCP tool name that was invoked
    status: Literal["done", "skipped", "failed"]
    detail: str | None = None  # reason for skip/fail, or summary on done


class ActionRunResult(BaseModel):
    """Structured output of one source's batched action run."""

    results: list[ActionResult] = Field(default_factory=list)


class SynthesizeResponse(BaseModel):
    """Output of the scheduled synthesize agent — drives the briefing feed.

    Memory is persisted by the agent itself during the run via its `store_memory` tool,
    so it is not part of this response."""

    summary: str
    briefing: list[BriefingEntry] = Field(default_factory=list)


class InteractiveResponse(BaseModel):
    """Output of the interactive chat agent — only the conversational reply.

    The interactive agent stores memory via its `store_memory` tool and does not emit
    briefing/raw-data; those are scheduled-synthesis concerns (see SynthesizeResponse)."""

    chat_reply: str
