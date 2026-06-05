"""Interactive agent tools — memory, permissions, MCP, and data retrieval."""

from __future__ import annotations

import logging
from typing import Any

from pydantic_ai import Agent, RunContext

from jarvis.agents.core.interactive.deps import InteractiveDeps
from jarvis.db.repositories.permission_repo import _UNSET

logger = logging.getLogger(__name__)


def register_tools(agent: Agent) -> None:
    """Attach memory, permission, and MCP tools to the interactive agent."""

    # --- MCP discovery and invocation tools (lazy loading) ---

    @agent.tool
    async def list_mcp_servers(ctx: RunContext[InteractiveDeps]) -> list[str]:
        """List all available MCP servers.

        Call this first to see which external services are connected (e.g. google,
        google-calendar, slack, github, atlassian). Then use list_mcp_tools to see
        what tools each server provides.
        """
        return ctx.deps.mcp_service.all_servers()

    @agent.tool
    async def list_mcp_tools(ctx: RunContext[InteractiveDeps], server: str) -> list[dict]:
        """List all tools available on a specific MCP server.

        Args:
            server: the MCP server name (from list_mcp_servers)

        Returns a list of tools with their name, description, and input schema.
        Use this to discover what actions you can take on each connected service.
        """
        try:
            mcp_server = ctx.deps.mcp_service.get_server(server)
            denied = ctx.deps.mcp_service.denied_tools(server)
            async with mcp_server:
                tools = await mcp_server.list_tools()
            return [
                {
                    "name": t.name,
                    "description": t.description or "(no description)",
                    "inputSchema": t.inputSchema,
                    "denied": t.name in denied,
                }
                for t in sorted(tools, key=lambda x: x.name)
            ]
        except KeyError:
            return [{"error": f"Unknown MCP server: {server}"}]
        except Exception as e:
            logger.exception("Failed to list tools for MCP server %s", server)
            return [{"error": f"Failed to connect to {server}: {e}"}]

    @agent.tool
    async def call_mcp_tool(
        ctx: RunContext[InteractiveDeps],
        server: str,
        tool: str,
        args: dict[str, Any],
    ) -> Any:
        """Call a tool on an MCP server.

        Args:
            server: the MCP server name (from list_mcp_servers)
            tool: the tool name (from list_mcp_tools)
            args: arguments to pass to the tool (must match the tool's inputSchema)

        Returns the tool's result, or an error dict if the call fails.
        """
        try:
            mcp_server = ctx.deps.mcp_service.get_server(server)
            denied = ctx.deps.mcp_service.denied_tools(server)
            if tool in denied:
                return {
                    "error": f"Tool '{tool}' is disabled by operator policy on server '{server}'"
                }
            async with mcp_server:
                result = await mcp_server.direct_call_tool(tool, args)
            return result
        except KeyError:
            return {"error": f"Unknown MCP server: {server}"}
        except Exception as e:
            logger.exception("Failed to call MCP tool %s.%s", server, tool)
            return {"error": f"Failed to call {server}.{tool}: {e}"}

    # --- Memory tools ---

    @agent.tool
    async def search_memory(ctx: RunContext[InteractiveDeps], query: str) -> list[dict]:
        """Search past knowledge and interactions. Use when you need context."""
        return await ctx.deps.memory_service.semantic_search(query)

    @agent.tool
    async def search_past_conversations(
        ctx: RunContext[InteractiveDeps], limit: int = 50
    ) -> list[dict]:
        """Fetch recent past conversations (user questions and assistant replies).

        Use when you need more context than what's provided in the conversation
        history header, or when the user references something from an older exchange.
        Returns up to `limit` recent interactions in chronological order.
        """
        return await ctx.deps.memory_service.get_recent_interactions(limit=limit)

    @agent.tool
    async def store_memory(
        ctx: RunContext[InteractiveDeps],
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

    # --- Permission management tools ---

    @agent.tool
    async def create_permission(
        ctx: RunContext[InteractiveDeps],
        description: str,
        source: str,
        constraints: dict,
        allowed_actions: list[str],
        max_matches: int | None = None,
    ) -> dict:
        """Create a new standing permission (automation rule).

        Call this ONLY after the user has explicitly confirmed they want the rule
        activated. Before calling, present the structured confirmation showing exactly
        what was understood (source, constraints, actions).

        Args:
            description: natural language summary, e.g. "archive Jenkins spam"
            source: which connected source this applies to (must be one of the discovered
                source agents, e.g. gmail, slack, github, atlassian)
            constraints: match rules using the constraint DSL:
                - {"field": "value"} — exact match
                - {"field_contains": "substring"} — substring match
                - {"field_matches": "regex"} — pattern match
                Fields mirror the source's result schema (e.g. gmail: sender, subject,
                snippet, body, labels).
            allowed_actions: CONCRETE MCP tool names to call when an item matches —
                resolved from the source's live toolset, NOT free-form verbs.
                e.g. ["archive_email", "mark_email_as_read"]. These run verbatim during
                scheduled polls, so only pass tools you have confirmed exist.
            max_matches: per-rule safety cap on how many items one scheduled poll may act
                on. Leave as None for the safe default. Set ONLY if the user explicitly
                asks to raise/remove the limit: a number for a custom cap, or 0 for
                unlimited ("handle all of them, don't cap this rule").

        Returns: the created permission record with its id, or {"error": ...} if the
        source is not a known agent or no actions were provided.
        """
        valid_sources = ctx.deps.agent_registry.list_agents()
        if source not in valid_sources:
            return {
                "error": (f"Unknown source '{source}'. Valid sources: {', '.join(valid_sources)}.")
            }
        if not allowed_actions:
            return {
                "error": (
                    "allowed_actions is empty — provide the concrete MCP tool name(s) "
                    "to call when an item matches."
                )
            }
        return await ctx.deps.permission_service.create(
            description=description,
            source=source,
            constraints=constraints,
            allowed_actions=allowed_actions,
            created_via=ctx.deps.session_id,
            max_matches=max_matches,
        )

    @agent.tool
    async def list_permissions(ctx: RunContext[InteractiveDeps]) -> list[dict]:
        """List all active standing permissions (automation rules).

        Call when the user asks "what can you do on your own?" or "what are my rules?"
        """
        return await ctx.deps.permission_service.list_active()

    @agent.tool
    async def find_permission(ctx: RunContext[InteractiveDeps], query: str) -> list[dict]:
        """Search active permissions by description (fuzzy match).

        Use this when the user refers to a rule by description rather than ID — e.g. to
        refine it with update_permission, or to resolve an overflow alert.
        """
        return await ctx.deps.permission_service.find_by_description(query)

    @agent.tool
    async def update_permission(
        ctx: RunContext[InteractiveDeps],
        permission_id: str,
        description: str | None = None,
        source: str | None = None,
        constraints: dict | None = None,
        allowed_actions: list[str] | None = None,
        max_matches: int | None = -1,
    ) -> dict:
        """Update an existing permission's constraints, actions, or match cap.

        Use when the user wants to refine a rule, e.g. "only archive if subject
        also contains 'build failed'". Pass only the fields that changed.

        max_matches controls the per-poll circuit-breaker cap. LEAVE AS -1 to keep the
        current value. Set ONLY if the user asks to change the limit:
          - 0    → unlimited ("handle all of them, stop capping this rule")
          - N>0  → cap at N per poll
          - None → reset to the safe default
        """
        if source is not None:
            valid_sources = ctx.deps.agent_registry.list_agents()
            if source not in valid_sources:
                return {
                    "error": (
                        f"Unknown source '{source}'. Valid sources: {', '.join(valid_sources)}."
                    )
                }
        result = await ctx.deps.permission_service.update(
            permission_id=permission_id,
            description=description,
            source=source,
            constraints=constraints,
            allowed_actions=allowed_actions,
            max_matches=_UNSET if max_matches == -1 else max_matches,
        )
        return result or {"error": "Permission not found"}
