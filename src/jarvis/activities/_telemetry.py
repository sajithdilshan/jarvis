"""Shared activity telemetry — token usage + raw-data persistence.

Plain functions (not a base class) so both AgentActivities' children and
InteractiveActivities can reuse them without inheritance. Each takes the
MemoryService explicitly. All persistence here is best-effort: telemetry
must never break the activity that triggered it.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone

from pydantic_ai.messages import ModelRequest, ToolReturnPart

from jarvis.models.memory import RawDataEntry
from jarvis.services.memory_service import MemoryService
from jarvis.services.telemetry_service import TelemetryService

logger = logging.getLogger(__name__)


async def record_usage(
    telemetry: TelemetryService,
    *,
    session_id: str,
    trigger: str,
    activity: str,
    agent: str,
    model: str,
    usage,
) -> None:
    """Persist a run's token usage. Best-effort — never break the activity."""
    try:
        await telemetry.record_usage(
            session_id=session_id,
            trigger=trigger,
            activity=activity,
            agent=agent,
            model=model,
            usage=usage,
        )
    except Exception as exc:  # telemetry must not affect the run
        logger.warning("token_usage record failed (%s): %s", activity, exc)


def persist_tool_raw_data_bg(memory: MemoryService, result, agent_name: str) -> None:
    """Fire-and-forget: persist MCP tool responses from the run as raw_data rows."""
    asyncio.create_task(persist_tool_raw_data(memory, result, agent_name))


async def persist_tool_raw_data(memory: MemoryService, result, agent_name: str) -> None:
    """Extract MCP tool responses from the run's message history and persist them."""
    now = datetime.now(timezone.utc)
    for msg in result.all_messages():
        if not isinstance(msg, ModelRequest):
            continue
        for part in msg.parts:
            if not isinstance(part, ToolReturnPart):
                continue
            if part.outcome != "success":
                continue
            content = part.content
            if not content:
                continue
            # default=str: some MCP tools return non-JSON-native types (e.g. datetime)
            # in their content — stringify them rather than crash the bg persist task.
            content_str = (
                json.dumps(content, default=str) if not isinstance(content, str) else content
            )
            if len(content_str) < 5:
                continue
            content_hash = hashlib.sha1(content_str.encode()).hexdigest()[:16]
            source_id = f"{part.tool_name}:{content_hash}"
            parsed = (
                json.loads(content_str)
                if content_str.startswith(("{", "["))
                else {"text": content_str}
            )
            if not isinstance(parsed, dict):
                parsed = {"items": parsed}
            entry = RawDataEntry(
                id=f"{agent_name}:{source_id}",
                source=agent_name,
                source_id=source_id,
                timestamp=part.timestamp or now,
                fetched_at=now,
                data=parsed,
                metadata={"tool_name": part.tool_name},
            )
            try:
                await memory.store_raw_data(entry)
            except Exception as exc:
                logger.warning(
                    "raw_data persist failed (%s/%s): %s",
                    agent_name,
                    part.tool_name,
                    exc,
                )
