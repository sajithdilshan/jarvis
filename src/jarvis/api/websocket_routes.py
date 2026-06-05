"""WebSocket route registration."""

from __future__ import annotations

import asyncpg
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from jarvis.api.websocket import relay_session


def register_websocket_routes(app: FastAPI, *, notify_pool: asyncpg.Pool) -> None:
    @app.websocket("/ws/{session_id}")
    async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()
        try:
            await relay_session(websocket, session_id, notify_pool)
        except WebSocketDisconnect:
            pass
