"""Entry point — boots the container, then runs the Temporal worker + FastAPI server.

A single process runs both so the API shares the worker's DB resources and Temporal
client. CRUD goes through the SQLAlchemy engine; the WebSocket relay LISTENs on a thin
asyncpg notify_pool on the same database that services NOTIFY.
"""

from __future__ import annotations

import asyncio
import logging

import uvicorn
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker
from temporalio.worker.workflow_sandbox import (
    SandboxedWorkflowRunner,
    SandboxRestrictions,
)

from jarvis.api.routes import create_app
from jarvis.config.containers import Container
from jarvis.config.logging_config import configure_logging
from jarvis.config.settings import load_settings
from jarvis.workflows.interactive_workflow import InteractiveChatWorkflow
from jarvis.workflows.main_workflow import MainAgentWorkflow
from jarvis.workflows.setup import ensure_schedule

logger = logging.getLogger(__name__)


async def run() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)

    logger.info(
        "Building DI container: default_model=%s interactive_model=%s "
        "model_override=%s task_queue=%s",
        settings.llm.default_model,
        settings.llm.interactive_model,
        settings.llm.model_override,
        settings.temporal.task_queue,
    )
    container = Container()
    container.config.from_dict(settings.model_dump())
    # Initialize async resources (creates the asyncpg pool + applies schema).
    await container.init_resources()
    # Alembic's env.py runs fileConfig() during migration, which resets the root logger
    # to alembic.ini's WARN/generic config — silencing app logs. Re-apply ours after.
    configure_logging(settings.log_level)

    # Activities depend on the async DB resources (engine/sessionmaker), so each
    # provider returns an awaitable that resolves once those are ready.
    source = await container.source_activities()
    synthesis = await container.synthesis_activities()
    briefing = await container.briefing_activities()
    permission = await container.permission_activities()
    interactive = await container.interactive_activities()
    logger.info("Activities created: source, synthesis, briefing, permission, interactive")

    # Pre-warm MCP servers once at startup so agents reuse live connections
    # instead of spawning/tearing down a subprocess per run.
    mcp_service = container.mcp_service()
    await mcp_service.start_all()

    client = await Client.connect(
        settings.temporal.host,
        namespace=settings.temporal.namespace,
        data_converter=pydantic_data_converter,
    )

    await ensure_schedule(
        client,
        settings.temporal.task_queue,
        cron=settings.schedule.cron,
        timezone=settings.schedule.timezone,
        enabled=settings.schedule.enabled,
    )

    # Pass heavy third-party modules through the workflow sandbox unchanged. They are
    # only touched by activities (which run outside the sandbox), and re-importing them
    # in the sandbox triggers circular-import errors (e.g. beartype via pydantic-ai).
    passthrough = SandboxRestrictions.default.with_passthrough_modules(
        "pydantic_ai", "beartype", "sentence_transformers", "asyncpg", "pgvector"
    )
    worker = Worker(
        client,
        task_queue=settings.temporal.task_queue,
        workflows=[MainAgentWorkflow, InteractiveChatWorkflow],
        activities=[
            source.list_registered_agents,
            source.get_poll_watermark,
            source.set_poll_watermark,
            source.run_sub_agent,
            synthesis.run_main_agent_synthesize,
            briefing.publish_briefing,
            briefing.report_source_failures,
            permission.execute_permissions,
            interactive.run_interactive_chat,
        ],
        workflow_runner=SandboxedWorkflowRunner(restrictions=passthrough),
    )
    # FastAPI server — shares the worker's Temporal client + DB resources. The relay
    # LISTENs on the thin notify_pool; route queries go through services.
    app = create_app(
        notify_pool=await container.notify_pool(),
        temporal_client=client,
        task_queue=settings.temporal.task_queue,
        static_dir=settings.ui.static_dir,
        ui_service=await container.ui_service(),
        permission_service=await container.permission_service(),
        conversation_service=await container.conversation_service(),
        briefing_service=await container.briefing_service(),
    )
    # log_config=None: keep uvicorn from installing its own handlers/format so its
    # logs propagate through our unified root handler (see configure_logging).
    api_config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=settings.port,
        log_level=settings.log_level.lower(),
        log_config=None,
    )
    api_server = uvicorn.Server(api_config)

    logger.info(
        "Worker on task queue '%s'; API on port %d",
        settings.temporal.task_queue,
        settings.port,
    )
    try:
        await asyncio.gather(worker.run(), api_server.serve())
    finally:
        await mcp_service.stop_all()
        await container.shutdown_resources()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
