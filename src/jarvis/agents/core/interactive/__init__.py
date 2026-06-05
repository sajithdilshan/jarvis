"""Interactive chat agent — MCP tools loaded lazily via discovery tools."""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic_ai import Agent

from jarvis.agents.core.interactive.deps import InteractiveDeps
from jarvis.agents.core.interactive.tools import register_tools
from jarvis.agents.model_factory import build_model
from jarvis.agents.registry import AgentRegistry
from jarvis.models.agent_io import InteractiveResponse
from jarvis.services.mcp_service import MCPService

logger = logging.getLogger(__name__)

_PROMPT = (Path(__file__).parent / "prompt.md").read_text()


def _render_prompt(registry: AgentRegistry, mcp_servers: list[str]) -> str:
    """Fill the prompt's placeholders from the live source schemas and MCP servers."""
    catalog = registry.source_catalog()
    lines = [f"- {source}: {', '.join(fields)}" for source, fields in catalog.items()]
    sources = ", ".join(catalog) or "your connected sources"
    servers = ", ".join(mcp_servers) or "(none configured)"
    return (
        _PROMPT.replace("{source_fields}", "\n".join(lines))
        .replace("{sources}", sources)
        .replace("{mcp_servers}", servers)
    )


def build_interactive_agent(
    model_spec: str, mcp_service: MCPService, registry: AgentRegistry
) -> Agent:
    """Build the interactive agent with lazy MCP tool loading.

    MCP tools are NOT attached upfront (would exceed token limits). Instead, the agent
    has tools to list available servers, list tools per server, and call any tool
    dynamically. This keeps the system prompt small while giving access to all MCPs.
    """
    # Bedrock prompt caching is opt-in: without these markers every turn is a full
    # cache miss. The system prompt + tool definitions are stable across turns (the
    # bulk of input tokens), so caching them cuts cost/latency on turn 2+. Conversation
    # history is volatile and intentionally left uncached. Bedrock-only keys, so gate on
    # the provider. cache_read_tokens/cache_write_tokens then flow into token_usage.
    model_settings = None
    if model_spec.startswith("bedrock:"):
        model_settings = {
            "bedrock_cache_instructions": True,
            "bedrock_cache_tool_definitions": True,
        }
    mcp_servers = mcp_service.all_servers()
    logger.info(
        "Building interactive agent model=%s mcp_servers=%s (lazy) output_type=%s "
        "model_settings=%s retries=%s",
        model_spec,
        mcp_servers,
        InteractiveResponse.__name__,
        model_settings,
        2,
    )
    agent = Agent(
        model=build_model(model_spec),
        system_prompt=_render_prompt(registry, mcp_servers),
        deps_type=InteractiveDeps,
        output_type=InteractiveResponse,
        model_settings=model_settings,
        defer_model_check=True,
        retries=2,
    )
    register_tools(agent)
    return agent
