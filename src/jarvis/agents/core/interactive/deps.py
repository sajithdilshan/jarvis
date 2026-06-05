"""Dependencies for the interactive chat agent."""

from __future__ import annotations

from dataclasses import dataclass

from jarvis.agents.registry import AgentRegistry
from jarvis.services.mcp_service import MCPService
from jarvis.services.memory_service import MemoryService
from jarvis.services.permission_service import PermissionService
from jarvis.services.progress_service import ProgressService


@dataclass
class InteractiveDeps:
    memory_service: MemoryService
    progress_service: ProgressService
    permission_service: PermissionService
    agent_registry: AgentRegistry
    mcp_service: MCPService
    session_id: str
