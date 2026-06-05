"""Progress events: insert a row and NOTIFY listeners (WebSocket relay forwards them)."""

from __future__ import annotations

import json

from jarvis.db.repositories.progress_repo import ProgressRepo


class ProgressService:
    def __init__(self, repo: ProgressRepo):
        self._repo = repo

    async def publish(self, session_id: str, status: str, data: dict | None = None) -> None:
        """Insert a progress row and NOTIFY the session channel (one transaction)."""
        envelope = {"type": "progress", "status": status}
        # Keep the NOTIFY envelope small (8KB cap). The full data is persisted to the
        # progress row; over the wire we only carry it if it stays tiny.
        if data is not None:
            compact = json.dumps(data)
            if len(compact.encode()) <= 1024:
                envelope["data"] = data
        payload = json.dumps(envelope)
        channel = f"jarvis_session_{session_id}"
        await self._repo.add_and_notify(session_id, status, data, channel, payload)

    async def get_progress(self, session_id: str) -> list[dict]:
        return await self._repo.list_for_session(session_id)
