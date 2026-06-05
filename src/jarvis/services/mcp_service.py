"""Manages MCP server connections, defined once in mcp/servers.yaml.

Servers are resolved by name and cached (one instance per name), so multiple agents
referencing the same server (e.g. gmail + calendar -> "google") share a connection.
"""

from __future__ import annotations

import logging
import os
import re
from contextlib import AsyncExitStack
from typing import Any

import yaml
from pydantic_ai.mcp import (
    CallToolFunc,
    MCPServer,
    MCPServerStdio,
    MCPServerStreamableHTTP,
    ToolResult,
)
from pydantic_ai.tools import RunContext

_ENV_RE = re.compile(r"\$\{(\w+)\}")

logger = logging.getLogger(__name__)


def _make_gate(server_name: str, denied: set[str]):
    """Build a process_tool_call gate that logs every call and blocks denied tools.

    The callback receives the de-prefixed tool name (pydantic_ai strips any
    tool_prefix before calling us), so we match bare names directly. This is the
    tamper-proof seam — exposure filtering alone is advisory. It also logs the
    request args and response so MCP traffic can be diffed against agent output.
    """

    async def gate(
        ctx: RunContext[Any],
        call_tool: CallToolFunc,
        name: str,
        args: dict[str, Any],
    ) -> ToolResult:
        if name in denied:
            logger.info("MCP[%s] DENIED tool=%s args=%s", server_name, name, args)
            return (
                f"Tool '{name}' on MCP server '{server_name}' is disabled by operator "
                f"policy and cannot be invoked."
            )
        logger.info("MCP[%s] -> tool=%s args=%s", server_name, name, args)
        result = await call_tool(name, args)
        logger.info("MCP[%s] <- tool=%s result=%r", server_name, name, result)
        return result

    return gate


class MCPService:
    def __init__(self, mcp_config_path: str):
        self._config = self._load_config(mcp_config_path)
        self._servers: dict[str, MCPServer] = {}
        self._warm_stack: AsyncExitStack | None = None

    async def start_all(self) -> None:
        """Open a long-lived connection to every configured server.

        pydantic_ai's MCPServer reference-counts its connection: the first
        ``async with`` spawns the subprocess / opens the HTTP session, and it is
        torn down only when the last scope exits. By holding one scope open here
        for the app's lifetime we pin the refcount at >=1, so the per-run
        ``async with agent:`` in activities just bumps the counter (no restart).
        """
        if self._warm_stack is not None:
            return
        stack = AsyncExitStack()
        for name in self._config.get("servers", {}):
            server = self.get_server(name)
            try:
                await stack.enter_async_context(server)
            except Exception:
                logger.exception("Failed to pre-warm MCP server '%s'", name)
        self._warm_stack = stack

    async def stop_all(self) -> None:
        """Release the long-lived connections opened by ``start_all``."""
        if self._warm_stack is None:
            return
        await self._warm_stack.aclose()
        self._warm_stack = None

    def get_server(self, name: str) -> MCPServer:
        if name not in self._servers:
            self._servers[name] = self._create_server(name)
        return self._servers[name]

    def all_servers(self) -> list[str]:
        """All configured server names from servers.yaml (order-stable)."""
        return list(self._config.get("servers", {}))

    def get_toolset(self, name: str):
        """Server toolset with operator-denied tools filtered out of exposure.

        Prefer this over `get_server` when attaching to an agent: it hides denied
        tools from the model (exposure seam). The invocation gate baked into the
        server object is the actual enforcement and applies either way.
        """
        server = self.get_server(name)
        denied = self.denied_tools(name)
        if not denied:
            return server
        return server.filtered(lambda ctx, tool_def: tool_def.name not in denied)

    def denied_tools(self, name: str) -> set[str]:
        """Operator-denied tool names for a server (from `deny_tools` in config)."""
        cfg = self._config.get("servers", {}).get(name, {})
        return set(cfg.get("deny_tools", []))

    def _create_server(self, name: str) -> MCPServer:
        servers = self._config.get("servers", {})
        if name not in servers:
            raise KeyError(f"MCP server '{name}' not found in config")
        cfg = servers[name]
        kind = cfg.get("type")
        denied = self.denied_tools(name)
        # Always attach the gate: it logs all MCP traffic and (if any) blocks denied tools.
        gate = _make_gate(name, denied)
        if kind == "http":
            return MCPServerStreamableHTTP(
                url=cfg["url"],
                headers=self._resolve_env(cfg.get("headers", {})),
                process_tool_call=gate,
            )
        if kind == "stdio":
            # Default init timeout is 5s, too short for an npx server that downloads its
            # package on first run. Allow per-server override via `timeout` in the config.
            return MCPServerStdio(
                command=cfg["command"],
                args=cfg.get("args", []),
                env=self._resolve_env(cfg.get("env", {})),
                timeout=cfg.get("timeout", 30),
                process_tool_call=gate,
            )
        raise ValueError(f"Unknown MCP server type for '{name}': {kind!r}")

    @staticmethod
    def _resolve_env(mapping: dict) -> dict:
        """Replace ${VAR} with environment variable values."""
        resolved = {}
        for key, value in mapping.items():
            if isinstance(value, str):
                resolved[key] = _ENV_RE.sub(lambda m: os.environ.get(m.group(1), m.group(0)), value)
            else:
                resolved[key] = value
        return resolved

    @staticmethod
    def _load_config(path: str) -> dict:
        with open(path) as f:
            return yaml.safe_load(f) or {}
