"""`jarvis-auth` — manage MCP server credentials.

All MCP OAuth state lives under ~/.jarvis/mcp-auth/<server>/, one dir per server, set via
each server's env in mcp/servers.yaml. docker-compose mounts that base dir into the
container, so a host-side login warms the container's token.

Subcommands:
  status            Show which MCP servers have their tokens configured.
  set KEY VALUE     Write a token to .env (e.g. `set GITHUB_TOKEN ghp_...`).
  gmail             Run the one-time Gmail OAuth browser flow.
  calendar          Run the one-time Google Calendar OAuth browser flow.
  <remote>          One subcommand per remote (mcp-remote) server in servers.yaml,
                    auto-discovered and named after the server key (e.g. `atlassian`).

OAuth subcommands accept --force, which clears the cached token first to force a fresh
browser login (needed when the refresh token has expired/been revoked — the flow
otherwise reuses the stale cache and never opens a browser). OAuth client keys are kept.

Token requirements are discovered from mcp/servers.yaml (the ${VAR} references in each
server's env), so adding a new server's tokens needs no CLI change.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from jarvis.cli.envfile import read_env, set_env

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILE = _REPO_ROOT / ".env"
_SERVERS_YAML = Path(os.environ.get("JARVIS_MCP_CONFIG", _REPO_ROOT / "mcp" / "servers.yaml"))
_MCP_AUTH_BASE = Path.home() / ".jarvis" / "mcp-auth"
_ENV_RE = re.compile(r"\$\{(\w+)\}")


def _expand(value: str) -> str:
    """Expand ${VAR} references in a config string using the current environment."""
    return _ENV_RE.sub(lambda m: os.environ.get(m.group(1), m.group(0)), value)


def _servers() -> dict[str, dict]:
    cfg = yaml.safe_load(_SERVERS_YAML.read_text()) if _SERVERS_YAML.exists() else {}
    return cfg.get("servers") or {}


def _server_env(name: str) -> dict[str, str]:
    """A server's env block with ${VAR} expanded against the current environment."""
    raw = (_servers().get(name) or {}).get("env") or {}
    return {k: _expand(v) for k, v in raw.items() if isinstance(v, str)}


def _is_remote(server: dict) -> bool:
    """True if a server is an mcp-remote bridge (its args invoke `mcp-remote`)."""
    return "mcp-remote" in (server.get("args") or [])


def _remote_servers() -> dict[str, dict]:
    """All mcp-remote servers, keyed by name (auto-discovered for CLI subcommands)."""
    return {n: s for n, s in _servers().items() if _is_remote(s)}


def _remote_config_dir(name: str) -> Path:
    """Resolve a remote server's MCP_REMOTE_CONFIG_DIR (default ~/.jarvis/mcp-auth/<name>).

    mcp-remote nests its actual state under <dir>/mcp-remote-<ver>/; callers glob the
    version subdirs beneath it.
    """
    raw = _server_env(name).get("MCP_REMOTE_CONFIG_DIR")
    return Path(raw) if raw else _MCP_AUTH_BASE / name


def _remote_url(server: dict) -> str:
    """The remote endpoint URL from a server's mcp-remote args (first http(s) arg)."""
    for arg in server.get("args") or []:
        if isinstance(arg, str) and arg.startswith("http"):
            return arg
    raise ValueError("no http(s) URL found in mcp-remote args")


def _required_env_by_server() -> dict[str, list[str]]:
    """Map each MCP server -> the ${VAR} env names it references."""
    out: dict[str, list[str]] = {}
    for name, server in _servers().items():
        vars_: list[str] = []
        for value in (server.get("env") or {}).values():
            if isinstance(value, str):
                vars_.extend(_ENV_RE.findall(value))
        for value in (server.get("headers") or {}).values():
            if isinstance(value, str):
                vars_.extend(_ENV_RE.findall(value))
        out[name] = sorted(set(vars_))
    return out


def _oauth_token_cached(server: str) -> bool | None:
    """Whether a server's OAuth token is cached. None if the server isn't OAuth-based.

    OAuth servers store a token at an env-configured path (gmail/calendar) or under a
    remote config dir (mcp-remote). The path-bearing ${VAR}s expand to HOME, so the
    generic env check can't see them — we verify the token file directly instead.
    """
    if _is_remote(_servers().get(server) or {}):
        return any(_remote_config_dir(server).glob("mcp-remote-*/*_tokens.json"))
    senv = _server_env(server)
    if "GMAIL_CREDENTIALS_PATH" in senv:
        return Path(senv["GMAIL_CREDENTIALS_PATH"]).exists()
    if "GOOGLE_CALENDAR_MCP_TOKEN_PATH" in senv:
        return Path(senv["GOOGLE_CALENDAR_MCP_TOKEN_PATH"]).exists()
    return None


def _cmd_status() -> int:
    env = {**read_env(_ENV_FILE), **{k: v for k, v in os.environ.items()}}
    print(f"Auth status (.env: {_ENV_FILE})\n")
    for server, keys in _required_env_by_server().items():
        cached = _oauth_token_cached(server)
        if cached is not None:
            mark = "✓" if cached else "✗"
            hint = "calendar" if server == "google-calendar" else server.replace("google", "gmail")
            detail = "OAuth token cached" if cached else f"run `jarvis-auth {hint}`"
            print(f"  {mark} {server:<14} {detail}")
            continue
        if not keys:
            print(f"  • {server:<14} (no tokens required)")
            continue
        missing = [k for k in keys if not env.get(k)]
        mark = "✓" if not missing else "✗"
        detail = "configured" if not missing else f"missing: {', '.join(missing)}"
        print(f"  {mark} {server:<14} {detail}")
    return 0


def _cmd_set(key: str, value: str) -> int:
    set_env(_ENV_FILE, key, value)
    print(f"✓ Set {key} in {_ENV_FILE}")
    return 0


def _cmd_gmail(force: bool = False) -> int:
    """Run the Gmail MCP server's one-time browser auth.

    Paths come from the `google` server's env in servers.yaml (GMAIL_OAUTH_PATH for the
    client keys, GMAIL_CREDENTIALS_PATH for the cached token). With force=True the cached
    token is deleted first so the flow re-prompts; the OAuth client keys are preserved.
    """
    senv = _server_env("google")
    keys = Path(senv["GMAIL_OAUTH_PATH"])
    token = Path(senv["GMAIL_CREDENTIALS_PATH"])
    token.parent.mkdir(parents=True, exist_ok=True)
    if not keys.exists():
        print(
            f"Missing {keys} — create a Google OAuth client first "
            "(see docs/gmail-mcp-setup.md).",
            file=sys.stderr,
        )
        return 1
    if force:
        token.unlink(missing_ok=True)
        print("Cleared cached Gmail token — forcing fresh login.")
    print("Launching Gmail OAuth (a browser window will open)…")
    env = {**os.environ, **senv}
    return subprocess.call(["npx", "-y", "@gongrzhe/server-gmail-autoauth-mcp", "auth"], env=env)


def _cmd_calendar(force: bool = False) -> int:
    """Run the Google Calendar MCP server's one-time browser auth.

    Paths come from the `google-calendar` server's env in servers.yaml
    (GOOGLE_OAUTH_CREDENTIALS for the client keys, GOOGLE_CALENDAR_MCP_TOKEN_PATH for the
    cached token). With force=True the cached token is deleted first; client keys are kept.
    """
    senv = _server_env("google-calendar")
    keys = Path(senv["GOOGLE_OAUTH_CREDENTIALS"])
    token = Path(senv["GOOGLE_CALENDAR_MCP_TOKEN_PATH"])
    token.parent.mkdir(parents=True, exist_ok=True)
    if not keys.exists():
        print(
            f"Missing {keys} — create a Google OAuth client first "
            "(see docs/google-calendar-mcp-setup.md).",
            file=sys.stderr,
        )
        return 1
    if force:
        token.unlink(missing_ok=True)
        print("Cleared cached Google Calendar token — forcing fresh login.")
    print("Launching Google Calendar OAuth (a browser window will open)…")
    env = {**os.environ, **senv}
    return subprocess.call(["npx", "-y", "@cocal/google-calendar-mcp", "auth"], env=env)


def _clear_remote_cache(name: str) -> int:
    """Delete a remote server's cached mcp-remote OAuth artifacts to force a fresh login.

    mcp-remote stores tokens/verifiers/client-info per version under
    <config_dir>/mcp-remote-<ver>/. Removing the whole config dir wipes ALL version
    subdirs together — leaving a stale verifier/client-info in an older version dir is
    what triggers "Invalid PKCE code_verifier". Returns the number of files removed.
    """
    base = _remote_config_dir(name)
    removed = sum(1 for p in base.glob("mcp-remote-*/*") if p.is_file())
    if base.exists():
        shutil.rmtree(base)
    return removed


def _cmd_remote(name: str, force: bool = False) -> int:
    """Run a remote (mcp-remote) server's OAuth flow via mcp-remote (opens a browser).

    Tokens are cached under the server's MCP_REMOTE_CONFIG_DIR (see servers.yaml), which
    docker-compose mounts into the container. Keep this process running until the browser
    flow completes and the token is written; Ctrl-C afterwards is fine.

    With force=True, the cached config dir is removed first. mcp-remote reuses any valid
    cache and won't re-prompt; clearing it is the only way to force a browser login when
    the refresh token itself has expired or been revoked.
    """
    server = _remote_servers()[name]
    base = _remote_config_dir(name)
    if force:
        cleared = _clear_remote_cache(name)
        print(f"Cleared {cleared} cached mcp-remote token file(s) — forcing fresh login.")
    base.mkdir(parents=True, exist_ok=True)
    print(f"Launching {name} OAuth via mcp-remote (a browser window will open)…")
    print("Complete the login in your browser, then Ctrl-C once the token is saved.")
    env = {**os.environ, "MCP_REMOTE_CONFIG_DIR": str(base)}
    return subprocess.call(["npx", "-y", "mcp-remote", _remote_url(server)], env=env)


def main() -> None:
    parser = argparse.ArgumentParser(prog="jarvis-auth", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Show which MCP servers have tokens configured")
    p_set = sub.add_parser("set", help="Write a token to .env")
    p_set.add_argument("key")
    p_set.add_argument("value")

    def _force_parser(name: str, help_text: str) -> None:
        p = sub.add_parser(name, help=help_text)
        p.add_argument(
            "--force",
            action="store_true",
            help="Clear the cached token first and force a fresh browser login",
        )

    _force_parser("gmail", "Run the one-time Gmail OAuth browser flow")
    _force_parser("calendar", "Run the one-time Google Calendar OAuth browser flow")
    # One subcommand per remote (mcp-remote) server, auto-discovered from servers.yaml.
    remote = _remote_servers()
    for name in remote:
        _force_parser(name, f"Run the one-time {name} OAuth browser flow (remote MCP)")

    args = parser.parse_args()
    if args.command == "status":
        sys.exit(_cmd_status())
    if args.command == "set":
        sys.exit(_cmd_set(args.key, args.value))
    if args.command == "gmail":
        sys.exit(_cmd_gmail(force=args.force))
    if args.command == "calendar":
        sys.exit(_cmd_calendar(force=args.force))
    if args.command in remote:
        sys.exit(_cmd_remote(args.command, force=args.force))


if __name__ == "__main__":
    main()
