"""Synthesize agent — reasons over aggregated sub-agent data; tools + deps."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from pydantic_ai import Agent

from jarvis.agents.core.synthesize.deps import SynthesizeAgentDeps
from jarvis.agents.core.synthesize.tools import register_tools
from jarvis.agents.model_factory import build_model
from jarvis.agents.registry import AgentRegistry
from jarvis.models.agent_io import SynthesizeResponse

logger = logging.getLogger(__name__)

_PROMPT = (Path(__file__).parent / "prompt.md").read_text()


def _render_prompt(registry: AgentRegistry) -> str:
    """Fill the synthesize-mode source-shapes placeholder from the live source schemas.

    Derived from the registry so adding a source needs no prompt edit.
    """
    lines = [
        f"- {source}: `{items_key}` — a list of items with fields: {', '.join(fields)}"
        for source, (items_key, fields) in registry.source_item_catalog().items()
    ]
    return _PROMPT.replace("{source_fields}", "\n".join(lines))


@lru_cache(maxsize=None)
def build_synthesize_agent(model_spec: str, registry: AgentRegistry) -> Agent:
    """Build (and cache) the synthesize agent for a given model spec + registry."""
    logger.info(
        "Building synthesize agent model=%s output_type=%s retries=%s",
        model_spec,
        SynthesizeResponse.__name__,
        2,
    )
    agent = Agent(
        model=build_model(model_spec),
        system_prompt=_render_prompt(registry),
        deps_type=SynthesizeAgentDeps,
        output_type=SynthesizeResponse,
        defer_model_check=True,
        retries=2,  # cap tool retries so a persistent failure doesn't loop forever
    )
    register_tools(agent)
    return agent


__all__ = ["build_synthesize_agent", "SynthesizeAgentDeps"]
