"""Synthesize agent tools — registered onto the agent in __init__.py."""

from __future__ import annotations

from pydantic_ai import Agent, RunContext

from jarvis.agents.core.synthesize.deps import SynthesizeAgentDeps


def register_tools(agent: Agent) -> None:
    """Attach the synthesize agent's tools."""

    @agent.tool
    async def search_memory(ctx: RunContext[SynthesizeAgentDeps], query: str) -> list[dict]:
        """Search past knowledge and interactions. Use when you need context."""
        return await ctx.deps.memory_service.semantic_search(query)

    @agent.tool
    async def store_memory(
        ctx: RunContext[SynthesizeAgentDeps],
        content: str,
        category: str,
        entities: list[str],
        importance: str,
    ) -> str:
        """Store important information for future recall.

        category: communication | task | decision | preference
        importance: low | medium | high
        """
        await ctx.deps.memory_service.store_chunk(
            content, category, entities, importance, session_id=ctx.deps.session_id
        )
        return "Stored"

    @agent.tool
    async def list_permissions(ctx: RunContext[SynthesizeAgentDeps]) -> list[dict]:
        """List all active standing permissions (automation rules).

        Check this before suggesting a new automation so you don't propose a rule that
        already exists.
        """
        return await ctx.deps.permission_service.list_active()

    @agent.tool
    async def find_permission(ctx: RunContext[SynthesizeAgentDeps], query: str) -> list[dict]:
        """Search active permissions by description (fuzzy match).

        Use to check whether a rule already covers a pattern before suggesting automating it.
        """
        return await ctx.deps.permission_service.find_by_description(query)
