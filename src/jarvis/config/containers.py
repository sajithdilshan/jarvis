"""Dependency-injection container.

Wires the asyncpg pool, services, and the agent registry. Services are added as they
are implemented; this is the single composition root for the worker and API.
"""

from __future__ import annotations

from dependency_injector import containers, providers

from jarvis.activities.briefing_activities import BriefingActivities
from jarvis.activities.interactive_activities import InteractiveActivities
from jarvis.activities.permission_activities import PermissionActivities
from jarvis.activities.source_activities import SourceActivities
from jarvis.activities.synthesis_activities import SynthesisActivities
from jarvis.agents.registry import AgentRegistry
from jarvis.db.engine import engine_resource, notify_pool_resource
from jarvis.db.repositories.briefing_feedback_repo import BriefingFeedbackRepo
from jarvis.db.repositories.briefing_log_repo import BriefingLogRepo
from jarvis.db.repositories.interaction_repo import InteractionRepo
from jarvis.db.repositories.memory_chunk_repo import MemoryChunkRepo
from jarvis.db.repositories.permission_repo import PermissionRepo
from jarvis.db.repositories.poll_watermark_repo import PollWatermarkRepo
from jarvis.db.repositories.progress_repo import ProgressRepo
from jarvis.db.repositories.raw_data_repo import RawDataRepo
from jarvis.db.repositories.token_usage_repo import TokenUsageRepo
from jarvis.db.repositories.ui_repo import UIRepo
from jarvis.services.briefing_service import BriefingService
from jarvis.services.conversation_service import ConversationService
from jarvis.services.embeddings import LocalEmbedder
from jarvis.services.mcp_service import MCPService
from jarvis.services.memory_service import MemoryService
from jarvis.services.permission_service import PermissionService
from jarvis.services.permission_execution_service import PermissionExecutionService
from jarvis.services.poll_watermark_service import PollWatermarkService
from jarvis.services.progress_service import ProgressService
from jarvis.services.telemetry_service import TelemetryService
from jarvis.services.ui_service import UIService


class Container(containers.DeclarativeContainer):
    config = providers.Configuration()

    # --- Database ---
    # The SQLAlchemy async engine + session factory back all CRUD. A separate thin
    # asyncpg pool (notify_pool) survives only for the WebSocket relay's LISTEN/NOTIFY,
    # which the ORM does not expose. Both are Resources (async create/dispose); the
    # engine resource also applies migrations on startup.
    db_sessionmaker = providers.Resource(
        engine_resource,
        dsn=config.postgres.dsn,
        max_size=config.postgres.pool_max_size,
    )

    notify_pool = providers.Resource(
        notify_pool_resource,
        dsn=config.postgres.dsn,
    )

    # --- Embedder (in-process, model lazy-loaded on first use) ---
    embedder = providers.Singleton(
        LocalEmbedder,
        model_name=config.embedding.model,
        dim=config.embedding.dim,
    )

    # --- Repositories (storage classes; each holds the sessionmaker, one session/call) ---
    memory_chunk_repo = providers.Singleton(MemoryChunkRepo, sessionmaker=db_sessionmaker)
    raw_data_repo = providers.Singleton(RawDataRepo, sessionmaker=db_sessionmaker)
    token_usage_repo = providers.Singleton(TokenUsageRepo, sessionmaker=db_sessionmaker)
    interaction_repo = providers.Singleton(InteractionRepo, sessionmaker=db_sessionmaker)
    poll_watermark_repo = providers.Singleton(PollWatermarkRepo, sessionmaker=db_sessionmaker)
    briefing_log_repo = providers.Singleton(BriefingLogRepo, sessionmaker=db_sessionmaker)
    briefing_feedback_repo = providers.Singleton(
        BriefingFeedbackRepo, sessionmaker=db_sessionmaker
    )
    permission_repo = providers.Singleton(PermissionRepo, sessionmaker=db_sessionmaker)
    progress_repo = providers.Singleton(ProgressRepo, sessionmaker=db_sessionmaker)
    ui_repo = providers.Singleton(UIRepo, sessionmaker=db_sessionmaker)

    # --- Core services (orchestrate repos + business logic; no raw DB access) ---
    memory_service = providers.Singleton(
        MemoryService,
        chunk_repo=memory_chunk_repo,
        raw_data_repo=raw_data_repo,
        embedder=embedder,
        dedup_threshold=config.embedding.dedup_threshold,
    )

    telemetry_service = providers.Singleton(
        TelemetryService,
        repo=token_usage_repo,
    )

    conversation_service = providers.Singleton(
        ConversationService,
        repo=interaction_repo,
    )

    poll_watermark_service = providers.Singleton(
        PollWatermarkService,
        repo=poll_watermark_repo,
    )

    briefing_service = providers.Singleton(
        BriefingService,
        repo=briefing_log_repo,
        feedback_repo=briefing_feedback_repo,
    )

    mcp_service = providers.Singleton(
        MCPService,
        mcp_config_path=config.mcp.config_path,
    )

    progress_service = providers.Singleton(
        ProgressService,
        repo=progress_repo,
    )

    ui_service = providers.Singleton(
        UIService,
        repo=ui_repo,
        briefing_repo=briefing_log_repo,
    )

    permission_service = providers.Singleton(
        PermissionService,
        repo=permission_repo,
    )

    # --- Agent registry (auto-discovers sources/, resolves MCP servers by name) ---
    agent_registry = providers.Singleton(
        AgentRegistry,
        mcp_service=mcp_service,
        default_model=config.llm.default_model,
        model_override=config.llm.model_override,
    )

    permission_execution_service = providers.Singleton(
        PermissionExecutionService,
        permission_service=permission_service,
        agent_registry=agent_registry,
    )

    # --- Activities (split by concern; each injected with only the deps it uses) ---
    source_activities = providers.Singleton(
        SourceActivities,
        memory_service=memory_service,
        progress_service=progress_service,
        agent_registry=agent_registry,
        poll_watermark_service=poll_watermark_service,
        telemetry_service=telemetry_service,
    )

    synthesis_activities = providers.Singleton(
        SynthesisActivities,
        memory_service=memory_service,
        progress_service=progress_service,
        agent_registry=agent_registry,
        telemetry_service=telemetry_service,
        permission_service=permission_service,
        default_model=config.llm.default_model,
    )

    briefing_activities = providers.Singleton(
        BriefingActivities,
        briefing_service=briefing_service,
        ui_service=ui_service,
    )

    permission_activities = providers.Singleton(
        PermissionActivities,
        execution_service=permission_execution_service,
    )

    interactive_activities = providers.Singleton(
        InteractiveActivities,
        memory_service=memory_service,
        conversation_service=conversation_service,
        telemetry_service=telemetry_service,
        progress_service=progress_service,
        ui_service=ui_service,
        permission_service=permission_service,
        agent_registry=agent_registry,
        briefing_service=briefing_service,
        mcp_service=mcp_service,
        interactive_model=config.llm.interactive_model,
        default_model=config.llm.default_model,
    )
