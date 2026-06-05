"""Slack source agent — self-contained plugin. The registry reads ``SPEC``."""

from jarvis.agents.base import AgentSpec, load_prompt
from jarvis.agents.sources.slack.schema import SlackSummary

SPEC = AgentSpec(
    name="slack",
    prompt=load_prompt(__file__),
    result_type=SlackSummary,
    items_key="messages",
    mcp_servers=["slack"],
    model_env="JARVIS_TOOL_AGENT_MODEL",
)
