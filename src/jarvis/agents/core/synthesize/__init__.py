"""Synthesize agent — reasons over aggregated sub-agent data; tools + deps."""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path

from pydantic_ai import Agent

from jarvis.agents.core.synthesize.deps import SynthesizeAgentDeps
from jarvis.agents.core.synthesize.tools import register_tools
from jarvis.agents.model_factory import build_model
from jarvis.agents.registry import AgentRegistry
from jarvis.models.agent_io import SynthesizeResponse

logger = logging.getLogger(__name__)

_HERE = Path(__file__).parent
_COMMENT_RE = re.compile(r"<!--.*?-->", flags=re.DOTALL)


def _read_surface(base_name: str) -> str:
    """Compose an editable prompt surface = tracked base + optional local override.

    The base file (e.g. ``prompt.md``, ``priority_policy.md``) is committed and generic.
    The improve-synthesizer skill NEVER edits the base; it writes learned personalizations
    to a gitignored ``*.local.md`` sibling (see ``.gitignore``) so sensitive/personal
    content stays off VCS. If that sibling exists, its content is appended after the base
    so it takes effect on the next poll with no commit. HTML comments (editor/skill
    guidance, not prompt text) are stripped from both.
    """
    base = _COMMENT_RE.sub("", (_HERE / base_name).read_text()).strip()
    local_path = _HERE / base_name.replace(".md", ".local.md")
    if not local_path.exists():
        return base
    local = _COMMENT_RE.sub("", local_path.read_text())
    # Drop the bookkeeping `last_optimized:` stamp line — it scopes the skill's feedback
    # window, it is not prompt content the model should read.
    local = "\n".join(
        ln for ln in local.splitlines() if not ln.strip().lower().startswith("last_optimized:")
    ).strip()
    if not local:
        return base
    # Learned personalizations refine/override the generic base; place them last so the
    # model reads them as the more specific, authoritative guidance.
    return f"{base}\n\n### Learned personalizations (local)\n\n{local}"


_PROMPT = _read_surface("prompt.md")


def _render_prompt(registry: AgentRegistry) -> str:
    """Fill the synthesize-mode placeholders: source shapes + the priority policy.

    Source shapes are derived from the registry so adding a source needs no prompt edit;
    the priority policy is composed from its own editable surface. Both the base prompt and
    the priority policy include any gitignored local overrides (see ``_read_surface``).
    """
    lines = [
        f"- {source}: `{items_key}` — a list of items with fields: {', '.join(fields)}"
        for source, (items_key, fields) in registry.source_item_catalog().items()
    ]
    return (
        _PROMPT.replace("{source_fields}", "\n".join(lines))
        .replace("{priority_policy}", _read_surface("priority_policy.md"))
    )


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
