"""AgentRegistry — auto-discovers source agents from agents/sources/ and builds them.

Discovery is the source of truth: each subpackage of ``agents.sources`` that exports a
``SPEC`` becomes an agent. No hardcoded list, no YAML.
"""

from __future__ import annotations

import importlib
import logging
import os
import pkgutil
import typing

from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_ai import Agent, ToolOutput

from jarvis.agents import sources
from jarvis.agents.base import AgentSpec
from jarvis.agents.model_factory import build_model
from jarvis.services.mcp_service import MCPService

logger = logging.getLogger(__name__)


def _list_item_model(field: FieldInfo) -> type[BaseModel] | None:
    """Return the inner BaseModel of a ``list[SomeModel]`` field, else None."""
    args = typing.get_args(field.annotation)
    inner = args[0] if args else field.annotation
    if isinstance(inner, type) and issubclass(inner, BaseModel):
        return inner
    return None


class AgentRegistry:
    def __init__(
        self,
        mcp_service: MCPService,
        default_model: str,
        model_override: str | None = None,
    ):
        self._mcp = mcp_service
        self._default_model = default_model
        self._model_override = model_override
        self._specs: dict[str, AgentSpec] = self._discover()
        self._agents: dict[str, Agent] = {}

    def _discover(self) -> dict[str, AgentSpec]:
        specs: dict[str, AgentSpec] = {}
        for mod in pkgutil.iter_modules(sources.__path__):
            pkg = importlib.import_module(f"jarvis.agents.sources.{mod.name}")
            spec = getattr(pkg, "SPEC", None)
            if spec is None:
                continue  # not an agent folder
            if spec.name != mod.name:
                raise ValueError(f"SPEC.name '{spec.name}' != folder '{mod.name}'")
            specs[spec.name] = spec
        return specs

    def get_agent(self, name: str) -> Agent:
        if name not in self._agents:
            self._agents[name] = self._build_agent(self._specs[name])
        return self._agents[name]

    def get_spec(self, name: str) -> AgentSpec:
        return self._specs[name]

    def list_agents(self) -> list[str]:
        """Pollable source agents (poll=True). Core agents are not discovered here."""
        return [name for name, spec in self._specs.items() if spec.poll]

    def all_mcp_servers(self) -> list[str]:
        """All MCP server names from servers.yaml (order-stable).

        Returns every server configured in the MCP service, not just those referenced
        by source agents — the interactive agent should have access to all tools.
        """
        return list(self._mcp.all_servers())

    def source_catalog(self) -> dict[str, list[str]]:
        """Map each source name to the match-fields on its per-item schema.

        Derived from each SPEC's result_type[items_key] inner model, so the interactive
        prompt's field list stays in sync with the schemas — no hand-maintained list.
        """
        catalog: dict[str, list[str]] = {}
        for name, spec in self._specs.items():
            field = spec.result_type.model_fields.get(spec.items_key)
            item_model = _list_item_model(field) if field else None
            if item_model is not None:
                catalog[name] = list(item_model.model_fields)
        return catalog

    def source_item_catalog(self) -> dict[str, tuple[str, list[str]]]:
        """Map each source name to (items_key, per-item field names).

        Like source_catalog but also exposes WHICH result field holds the item list, so the
        synthesize prompt can tell the agent which array to read per source — kept in sync
        with the schemas, no hand-maintained list.
        """
        catalog: dict[str, tuple[str, list[str]]] = {}
        for name, spec in self._specs.items():
            field = spec.result_type.model_fields.get(spec.items_key)
            item_model = _list_item_model(field) if field else None
            if item_model is not None:
                catalog[name] = (spec.items_key, list(item_model.model_fields))
        return catalog

    def synthesize_agent(self) -> Agent:
        """The core synthesize agent, built against this registry's default model.

        Core agents aren't SPEC-discovered (they have bespoke deps/tools), but the
        registry stays the single entry point for getting *any* agent — it injects the
        model it already owns so callers don't re-thread it. Imported lazily to avoid a
        cycle (the builder imports AgentRegistry).
        """
        from jarvis.agents.core.synthesize import build_synthesize_agent

        return build_synthesize_agent(self._default_model, self)

    def interactive_agent(self, model_spec: str | None = None) -> Agent:
        """The core interactive chat agent, with every source's MCP servers attached.

        ``model_spec`` lets the caller pass an interactive-specific model override;
        falls back to the registry's default. The MCP service is injected from the
        registry. Imported lazily to avoid a cycle.
        """
        from jarvis.agents.core.interactive import build_interactive_agent

        return build_interactive_agent(model_spec or self._default_model, self._mcp, self)

    def model_for(self, name: str) -> str:
        """The model spec a given source agent resolves to (for usage telemetry).

        Resolution: global override > spec.model > spec.model_env's value > default.
        """
        spec = self._specs[name]
        env_model = os.environ.get(spec.model_env) if spec.model_env else None
        return self._model_override or spec.model or env_model or self._default_model

    def _build_agent(self, spec: AgentSpec) -> Agent:
        model_spec = self.model_for(spec.name)
        toolsets = [self._mcp.get_toolset(n) for n in spec.mcp_servers]
        logger.info(
            "Building source agent name=%s model=%s mcp_servers=%s output_type=%s poll=%s",
            spec.name,
            model_spec,
            spec.mcp_servers,
            spec.result_type.__name__,
            spec.poll,
        )
        agent = Agent(
            model=build_model(model_spec),
            system_prompt=spec.prompt,
            toolsets=toolsets,
            # ToolOutput forces the result through a dedicated tool call (structured JSON
            # from the provider) instead of free text. Weak callers like Nova Lite otherwise
            # wrap structured output in ```json fences that fail parsing. Nova supports
            # tool_choice but not native JSON-schema output, so this is the reliable mode.
            output_type=ToolOutput(spec.result_type),
            defer_model_check=True,  # don't require provider creds until run time
        )
        if spec.register_tools is not None:
            spec.register_tools(agent)
        return agent
