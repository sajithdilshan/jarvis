"""FastAPI app composition."""

from __future__ import annotations

import asyncpg
from fastapi import FastAPI
from temporalio.client import Client

from jarvis.api.permission_routes import register_permission_routes
from jarvis.api.session_routes import register_session_routes
from jarvis.api.static_routes import register_static_routes
from jarvis.api.view_routes import register_view_routes
from jarvis.api.websocket_routes import register_websocket_routes
from jarvis.services.briefing_service import BriefingService
from jarvis.services.conversation_service import ConversationService
from jarvis.services.permission_service import PermissionService
from jarvis.services.ui_service import UIService


def create_app(
    notify_pool: asyncpg.Pool,
    temporal_client: Client,
    task_queue: str,
    static_dir: str,
    ui_service: UIService,
    conversation_service: ConversationService,
    briefing_service: BriefingService,
    permission_service: PermissionService | None = None,
) -> FastAPI:
    app = FastAPI(title="Jarvis")
    register_session_routes(
        app,
        temporal_client=temporal_client,
        task_queue=task_queue,
        conversation_service=conversation_service,
    )
    register_permission_routes(app, permission_service=permission_service)
    register_view_routes(
        app,
        ui_service=ui_service,
        briefing_service=briefing_service,
    )
    register_websocket_routes(app, notify_pool=notify_pool)
    register_static_routes(app, static_dir=static_dir)
    return app
