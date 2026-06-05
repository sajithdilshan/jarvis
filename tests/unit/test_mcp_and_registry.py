"""Unit tests for MCP env resolution, model factory, and agent discovery."""

import os

from jarvis.agents.model_factory import build_model
from jarvis.services.mcp_service import MCPService


def test_model_factory_passthrough():
    assert build_model("openai:gpt-5.5") == "openai:gpt-5.5"


def test_model_factory_bedrock():
    m = build_model("bedrock:arn:aws:bedrock:eu-central-1:1:application-inference-profile/x")
    assert type(m).__name__ == "BedrockConverseModel"


def test_mcp_env_resolution(tmp_path, monkeypatch):
    monkeypatch.setenv("MYTOK", "secret123")
    cfg = tmp_path / "servers.yaml"
    cfg.write_text(
        "servers:\n"
        "  demo:\n"
        "    type: http\n"
        "    url: https://example/mcp\n"
        "    headers:\n"
        '      Authorization: "Bearer ${MYTOK}"\n'
    )
    svc = MCPService(str(cfg))
    server = svc.get_server("demo")
    # same name returns the cached instance
    assert svc.get_server("demo") is server


def test_registry_discovers_gmail(monkeypatch):
    monkeypatch.setenv("GOOGLE_TOKEN", "t")
    monkeypatch.setenv("GOOGLE_MCP_URL", "http://localhost/mcp")
    repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
    from jarvis.agents.registry import AgentRegistry

    reg = AgentRegistry(
        MCPService(os.path.join(repo_root, "mcp", "servers.yaml")),
        "openai:gpt-5.5",
    )
    assert "gmail" in reg.list_agents()
