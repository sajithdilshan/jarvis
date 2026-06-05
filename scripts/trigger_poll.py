"""Manually trigger one scheduled poll and print the result.

Usage (worker must be running separately):
    uv run python scripts/trigger_poll.py
"""

from __future__ import annotations

import asyncio
import os
import sys

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from jarvis.models.session import WorkflowInput
from jarvis.workflows.main_workflow import MainAgentWorkflow


async def main() -> None:
    host = os.environ.get("TEMPORAL_HOST", "localhost:4004")
    session_id = sys.argv[1] if len(sys.argv) > 1 else "manual-poll"
    client = await Client.connect(host, data_converter=pydantic_data_converter)
    result = await client.execute_workflow(
        MainAgentWorkflow.run,
        WorkflowInput(session_id=session_id, trigger="scheduled"),
        id=f"jarvis-{session_id}",
        task_queue="jarvis-agent-queue",
    )
    print("WORKFLOW RESULT:", result)


if __name__ == "__main__":
    asyncio.run(main())
