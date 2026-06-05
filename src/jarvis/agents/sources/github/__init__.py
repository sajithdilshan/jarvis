"""GitHub source agent — self-contained plugin. The registry reads ``SPEC``."""

from jarvis.agents.base import AgentSpec, load_prompt
from jarvis.agents.sources.github.schema import GithubSummary

SPEC = AgentSpec(
    name="github",
    prompt=load_prompt(__file__),
    result_type=GithubSummary,
    items_key="notifications",
    mcp_servers=["github"],
    model_env="JARVIS_TOOL_AGENT_MODEL",
)
