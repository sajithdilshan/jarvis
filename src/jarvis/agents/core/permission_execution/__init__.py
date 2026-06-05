"""Permission-execution agent.

Standing permissions are executed per-source on the source's own agent (so the right
MCP toolset and model run each action). This module owns the task prompt and the batched
run logic; the activity layer handles matching, audit, and briefing aggregation.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic_ai import Agent, ToolOutput

from jarvis.models.agent_io import ActionResult, ActionRunResult

logger = logging.getLogger(__name__)

_PROMPT = (Path(__file__).parent / "prompt.md").read_text()


# Per-item fields that carry no human meaning — skipped when describing an item.
_NOISE_FIELDS = {"id", "raw_data_id", "url", "_permission"}


def _describe_item(item: dict) -> str:
    """Generate a short, human-readable description of an item — source-agnostic.

    Builds the label from the item's own short string fields rather than hardcoding
    per-source shapes, so a new source agent works here with no edit. Falls back to the
    item's id when it has no descriptive text.
    """
    parts = [
        f"{key}: {value}"
        for key, value in item.items()
        if key not in _NOISE_FIELDS
        and isinstance(value, str)
        and value.strip()
        and len(value) <= 120
    ]
    return ", ".join(parts[:3]) or str(item.get("id", "item"))


def _render_task(by_id: dict) -> str:
    """Build the action task from the live matched items + their permissions."""
    lines = []
    for item_id, ctx in by_id.items():
        tools = ctx["perm"].get("allowed_actions", [])
        intent = ctx["perm"].get("description", "")
        desc = _describe_item(ctx["item"])
        lines.append(f'- item_id={item_id} ({desc}): call {", ".join(tools)} — intent: "{intent}"')
    return _PROMPT.replace("{actions}", "\n".join(lines))


async def run_source_actions(agent: Agent, source: str, by_id: dict) -> list[ActionResult]:
    """Run ALL matched actions for one source in a single batched agent run.

    The agent calls only the stored MCP tool names, using each rule's description as the
    intent to pick tool arguments (e.g. which Gmail labels to change). It returns a
    per-item status; if a named tool is unavailable or it is not confident, it skips and
    reports rather than guessing.
    """
    task = _render_task(by_id)
    try:
        async with agent:
            result = await agent.run(task, output_type=ToolOutput(ActionRunResult))
        return result.output.results
    except Exception as exc:
        logger.warning("Batched action run failed for %s: %s", source, exc)
        # Report every intended action as failed so nothing is silently dropped.
        return [
            ActionResult(item_id=item_id, tool=tool, status="failed", detail=str(exc))
            for item_id, ctx in by_id.items()
            for tool in ctx["perm"].get("allowed_actions", [])
        ]


__all__ = ["run_source_actions"]
