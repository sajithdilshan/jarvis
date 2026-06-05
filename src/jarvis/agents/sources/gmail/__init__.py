"""Gmail source agent — self-contained plugin. The registry reads ``SPEC``."""

from jarvis.agents.base import AgentSpec, load_prompt
from jarvis.agents.sources.gmail.schema import GmailSummary

SPEC = AgentSpec(
    name="gmail",
    prompt=load_prompt(__file__),
    result_type=GmailSummary,
    items_key="emails",
    mcp_servers=["google"],
    model_env="JARVIS_TOOL_AGENT_MODEL",
)
