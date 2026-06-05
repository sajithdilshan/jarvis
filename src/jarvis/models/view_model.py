"""Server-Driven UI protocol: the ViewModel tree the client renders.

Built deterministically from briefing_log (see ``briefing_entry_node``) and served by
/view-model; the Preact client replaces its tree wholesale on each fetch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from jarvis.models.agent_io import BriefingEntry


class Action(BaseModel):
    label: str
    # An action is EITHER a link (opens `url` in a new tab, no agent round-trip) OR an
    # intent (sent to the agent). Prefer `url` for pure navigation (open PR, open email).
    intent: str | None = None  # semantic name, e.g. "expand_email"
    url: str | None = None  # canonical link; client opens it directly
    args: dict[str, Any] = Field(default_factory=dict)
    style: Literal["primary", "default", "danger"] = "default"


class Node(BaseModel):
    id: str  # STABLE id — patches reference this
    type: str  # component type, e.g. "briefing_entry"
    props: dict[str, Any] = Field(default_factory=dict)
    actions: list[Action] = Field(default_factory=list)
    children: list["Node"] = Field(default_factory=list)
    ts: str | None = None  # ISO timestamp for recency sort (newest first)


class ViewModel(BaseModel):
    """Full current tree — rebuilt from briefing_log and served by /view-model."""

    regions: dict[str, list[Node]] = Field(default_factory=dict)  # region_id -> ordered nodes


def briefing_entry_node(entry: "BriefingEntry") -> Node:
    """Build the canonical feed Node for a briefing entry.

    Single source of truth for the briefing_entry -> ViewModel mapping, shared by the
    publish_briefing activity and the /view-model endpoint (both build the feed the same
    way; /view-model rebuilds it straight from briefing_log)."""
    return Node(
        id=entry.id,
        type="briefing_entry",
        props={
            "narrative": entry.narrative,
            "tier": entry.tier,
            "category": entry.category,
            "source": entry.source,
            "priority": entry.priority,
            "context": entry.context,
            "permission_ref": entry.permission_ref,
        },
        actions=[Action(label=ref.label, url=ref.url) for ref in entry.refs],
        ts=entry.ts,
    )
