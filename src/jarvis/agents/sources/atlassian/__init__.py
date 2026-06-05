"""Atlassian source agent — self-contained plugin. The registry reads ``SPEC``."""

from jarvis.agents.base import AgentSpec, load_prompt
from jarvis.agents.sources.atlassian.schema import AtlassianSummary

SPEC = AgentSpec(
    name="atlassian",
    prompt=load_prompt(__file__),
    result_type=AtlassianSummary,
    mcp_servers=["atlassian"],
    model_env="JARVIS_TOOL_AGENT_MODEL",
)
