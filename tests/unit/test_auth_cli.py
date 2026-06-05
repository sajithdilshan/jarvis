"""Phase 5: auth CLI .env read/write helpers + server token discovery."""

from pathlib import Path

from jarvis.cli.envfile import read_env, set_env


def test_set_env_updates_in_place_and_appends(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("# header\nGITHUB_TOKEN=old\nSLACK_MCP_XOXC_TOKEN=x\n")

    set_env(env, "GITHUB_TOKEN", "new")  # update existing
    set_env(env, "NEW_KEY", "val")  # append

    values = read_env(env)
    assert values["GITHUB_TOKEN"] == "new"
    assert values["NEW_KEY"] == "val"
    assert values["SLACK_MCP_XOXC_TOKEN"] == "x"
    # Comments are preserved and not parsed as keys.
    assert env.read_text().startswith("# header")
    assert "#" not in values


def test_read_env_missing_file_is_empty(tmp_path: Path):
    assert read_env(tmp_path / "nope.env") == {}


def test_required_env_by_server_reads_yaml(tmp_path: Path, monkeypatch):
    yaml_path = tmp_path / "servers.yaml"
    yaml_path.write_text(
        "servers:\n"
        "  github:\n"
        "    type: http\n"
        "    headers:\n"
        '      Authorization: "Bearer ${GITHUB_TOKEN}"\n'
        "  google:\n"
        "    type: stdio\n"
        "    command: npx\n"
    )
    monkeypatch.setattr("jarvis.cli.auth._SERVERS_YAML", yaml_path)
    from jarvis.cli.auth import _required_env_by_server

    mapping = _required_env_by_server()
    assert mapping["github"] == ["GITHUB_TOKEN"]
    assert mapping["google"] == []  # OAuth-based, no env tokens
