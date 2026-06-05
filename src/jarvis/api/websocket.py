"""WebSocket relay: bridge Postgres NOTIFY -> browser socket.

Each browser opens one socket for its session. The relay LISTENs on two channels:
the per-session channel (chat/click results target it) and the shared ``default``
channel (scheduled background refreshes broadcast there). Every envelope is small
(feed_refresh, chat_token, progress) and forwarded verbatim.
"""

from __future__ import annotations

import asyncio
import json

import asyncpg
from fastapi import WebSocket

from jarvis.services.ui_service import DEFAULT_CHANNEL, UIService


async def _forward(websocket: WebSocket, queue: asyncio.Queue) -> None:
    """Drain the NOTIFY queue to the socket."""
    while True:
        envelope = await queue.get()
        await websocket.send_json(envelope)


async def _drain_incoming(websocket: WebSocket) -> None:
    """Read (and ignore) client frames purely to detect disconnect.

    The relay is server->client only, but without consuming incoming frames we'd never
    notice the browser closing the socket — the forward loop would block forever on the
    queue while holding a pooled DB connection (a leak that exhausts the pool).
    """
    while True:
        await websocket.receive()  # raises WebSocketDisconnect when the client closes


async def relay_session(websocket: WebSocket, session_id: str, pool: asyncpg.Pool) -> None:
    """Forward every notification on the session + default channels to the socket.

    Runs the forwarder alongside a disconnect-detector; whichever finishes first (a send
    error or the client closing) tears the other down, releasing the DB connection.
    """
    queue: asyncio.Queue = asyncio.Queue()

    def _on_notify(_conn, _pid, _channel, payload: str) -> None:
        queue.put_nowait(json.loads(payload))

    channels = [
        UIService.channel_name(session_id),
        UIService.channel_name(DEFAULT_CHANNEL),
    ]
    async with pool.acquire() as conn:
        for ch in channels:
            await conn.add_listener(ch, _on_notify)
        tasks = [
            asyncio.create_task(_forward(websocket, queue)),
            asyncio.create_task(_drain_incoming(websocket)),
        ]
        try:
            # When either task ends (disconnect or send failure), stop both.
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in tasks:
                t.cancel()
            for ch in channels:
                await conn.remove_listener(ch, _on_notify)
