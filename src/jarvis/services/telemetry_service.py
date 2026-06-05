"""TelemetryService — persist per-call LLM token usage."""

from __future__ import annotations

from jarvis.db.repositories.token_usage_repo import TokenUsageRepo


class TelemetryService:
    def __init__(self, repo: TokenUsageRepo):
        self._repo = repo

    async def record_usage(
        self,
        *,
        session_id: str,
        trigger: str,
        activity: str,
        agent: str,
        model: str,
        usage,
    ) -> None:
        """Persist one LLM call's token usage. ``usage`` is a PydanticAI RunUsage; read
        its fields defensively so a missing attribute never breaks the activity."""
        g = lambda name: int(getattr(usage, name, 0) or 0)
        await self._repo.record(
            session_id=session_id,
            trigger=trigger,
            activity=activity,
            agent=agent,
            model=model,
            input_tokens=g("input_tokens"),
            output_tokens=g("output_tokens"),
            cache_read_tokens=g("cache_read_tokens"),
            cache_write_tokens=g("cache_write_tokens"),
            requests=g("requests"),
            tool_calls=g("tool_calls"),
        )
