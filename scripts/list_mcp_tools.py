"""List all tools exposed by each configured MCP server.

Connects to every server in mcp/servers.yaml (cold-starting it), enumerates its
tools, and prints them grouped by server — copy names straight into `deny_tools`.

Usage:  uv run python scripts/list_mcp_tools.py [server_name ...]
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from jarvis.services.mcp_service import MCPService

# Load .env so server creds (Slack/GitHub tokens) are present before connecting.
load_dotenv()

# Put this scripts/ dir on PATH so the locally-fetched `github-mcp-server` binary
# (called by bare name in servers.yaml) resolves without a manual PATH prefix.
os.environ["PATH"] = str(Path(__file__).resolve().parent) + os.pathsep + os.environ.get("PATH", "")


async def main() -> None:
    svc = MCPService("mcp/servers.yaml")
    names = sys.argv[1:] or list(svc._config.get("servers", {}))
    for name in names:
        server = svc.get_server(name)
        print(f"\n=== {name} ===")
        try:
            async with server:
                tools = await server.list_tools()
        except Exception as e:  # noqa: BLE001 — surface per-server failures, keep going
            print(f"  ! failed to connect: {e}")
            continue
        for t in sorted(tools, key=lambda x: x.name):
            desc = (t.description or "").strip().splitlines()
            summary = desc[0] if desc else "(no description)"
            print(f"  - {t.name}: {summary}")


if __name__ == "__main__":
    asyncio.run(main())
