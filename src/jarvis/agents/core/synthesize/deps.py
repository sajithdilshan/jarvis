"""Dependencies injected into the synthesize agent's tools (PydanticAI ``deps``)."""

from __future__ import annotations

from dataclasses import dataclass

from jarvis.services.memory_service import MemoryService
from jarvis.services.permission_service import PermissionService


@dataclass
class SynthesizeAgentDeps:
    memory_service: MemoryService
    permission_service: PermissionService
    session_id: str
