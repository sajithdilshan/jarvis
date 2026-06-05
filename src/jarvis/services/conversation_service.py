"""ConversationService — interaction (chat) history."""

from __future__ import annotations

from jarvis.db.repositories.interaction_repo import InteractionRepo


class ConversationService:
    def __init__(self, repo: InteractionRepo):
        self._repo = repo

    async def record_interaction(
        self, session_id: str, role: str, content: str, metadata: dict | None = None
    ) -> None:
        await self._repo.add(session_id, role, content, metadata or {})

    async def get_recent_interactions(self, limit: int = 20) -> list[dict]:
        return await self._repo.recent(limit)

    async def get_recent_messages(
        self, limit: int = 10, before_id: int | None = None
    ) -> list[dict]:
        """Chat thread page: ``{id, role, text, ts}`` oldest-first.

        ``before_id`` pages backwards; omit it for the newest messages.
        """
        return await self._repo.recent_messages(limit, before_id)
