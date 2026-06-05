"""AgentSpec — the plugin contract every source agent exports as ``SPEC``."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from pydantic import BaseModel


@dataclass(frozen=True)
class AgentSpec:
    name: str  # must match the source folder name
    prompt: str  # system prompt (usually from prompt.md)
    result_type: type[BaseModel]  # the schema class itself — no string registry
    items_key: str = "items"  # which result field holds the actionable item list
    mcp_servers: list[str] = field(default_factory=list)  # names from mcp/servers.yaml
    register_tools: Callable | None = None  # optional tools.py:register(agent)
    model: str | None = None  # optional per-agent model override
    model_env: str | None = None  # env var name holding a model spec (e.g. from .env)
    poll: bool = True  # included in scheduled fan-out?


def load_prompt(spec_file: str) -> str:
    """Read ``prompt.md`` sitting next to a source's ``__init__.py``."""
    return (Path(spec_file).parent / "prompt.md").read_text()
