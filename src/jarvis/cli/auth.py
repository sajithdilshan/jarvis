"""`jarvis-auth` — manage MCP server credentials.

Subcommands:
  status            Show which MCP servers have their tokens configured.
  set KEY VALUE     Write a token to .env (e.g. `set GITHUB_TOKEN ghp_...`).
  gmail             Run the one-time Gmail OAuth browser flow (writes ~/.gmail-mcp).
  calendar          Run the one-time Google Calendar OAuth flow (writes ~/.config/google-calendar-mcp).
  atlassian         Run the one-time Atlassian OAuth browser flow (writes ~/.mcp-auth).

Token requirements are discovered from mcp/servers.yaml (the ${VAR} references in each
server's env), so adding a new server's tokens needs no CLI change.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

from jarvis.cli.envfile import read_env, set_env

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILE = _REPO_ROOT / ".env"
_SERVERS_YAML = Path(os.environ.get("JARVIS_MCP_CONFIG", _REPO_ROOT / "mcp" / "servers.yaml"))
_GMAIL_DIR = Path.home() / ".gmail-mcp"
_GCAL_DIR = Path.home() / ".google-calendar-mcp"
_GCAL_KEYS = _GCAL_DIR / "gcp-oauth.keys.json"
_GCAL_TOKENS = Path.home() / ".config" / "google-calendar-mcp" / "tokens.json"
_MCP_AUTH_DIR = Path.home() / ".mcp-auth"
_ATLASSIAN_MCP_URL = "https://mcp.atlassian.com/v1/mcp"
_ENV_RE = re.compile(r"\$\{(\w+)\}")


def _required_env_by_server() -> dict[str, list[str]]:
    """Map each MCP server -> the ${VAR} env names it references."""
    cfg = yaml.safe_load(_SERVERS_YAML.read_text()) if _SERVERS_YAML.exists() else {}
    out: dict[str, list[str]] = {}
    for name, server in (cfg.get("servers") or {}).items():
        vars_: list[str] = []
        for value in (server.get("env") or {}).values():
            if isinstance(value, str):
                vars_.extend(_ENV_RE.findall(value))
        for value in (server.get("headers") or {}).values():
            if isinstance(value, str):
                vars_.extend(_ENV_RE.findall(value))
        out[name] = sorted(set(vars_))
    return out


def _cmd_status() -> int:
    env = {**read_env(_ENV_FILE), **{k: v for k, v in os.environ.items()}}
    print(f"Auth status (.env: {_ENV_FILE})\n")
    for server, keys in _required_env_by_server().items():
        # Google Calendar's only ${VAR} is HOME (a path, always set), so the generic env
        # check below is meaningless — verify the cached OAuth token instead.
        if server == "google-calendar":
            ok = _GCAL_TOKENS.exists()
            mark = "✓" if ok else "✗"
            detail = "OAuth token cached" if ok else "run `jarvis-auth calendar`"
            print(f"  {mark} {server:<8} {detail}")
            continue
        if not keys:
            # Token-less server (e.g. Gmail uses OAuth files, not env vars).
            if server in ("google", "gmail"):
                ok = (_GMAIL_DIR / "credentials.json").exists()
                mark = "✓" if ok else "✗"
                detail = "OAuth token cached" if ok else "run `jarvis-auth gmail`"
                print(f"  {mark} {server:<8} {detail}")
            elif server == "atlassian":
                ok = _MCP_AUTH_DIR.exists() and any(_MCP_AUTH_DIR.iterdir())
                mark = "✓" if ok else "✗"
                detail = "OAuth token cached" if ok else "run `jarvis-auth atlassian`"
                print(f"  {mark} {server:<8} {detail}")
            else:
                print(f"  • {server:<8} (no tokens required)")
            continue
        missing = [k for k in keys if not env.get(k)]
        mark = "✓" if not missing else "✗"
        detail = "configured" if not missing else f"missing: {', '.join(missing)}"
        print(f"  {mark} {server:<8} {detail}")
    return 0


def _cmd_set(key: str, value: str) -> int:
    set_env(_ENV_FILE, key, value)
    print(f"✓ Set {key} in {_ENV_FILE}")
    return 0


def _cmd_gmail() -> int:
    """Run the Gmail MCP server's one-time browser auth."""
    _GMAIL_DIR.mkdir(exist_ok=True)
    if not (_GMAIL_DIR / "gcp-oauth.keys.json").exists():
        print(
            "Missing ~/.gmail-mcp/gcp-oauth.keys.json — create a Google OAuth client "
            "first (see docs/gmail-mcp-setup.md).",
            file=sys.stderr,
        )
        return 1
    print("Launching Gmail OAuth (a browser window will open)…")
    return subprocess.call(["npx", "-y", "@gongrzhe/server-gmail-autoauth-mcp", "auth"])


def _cmd_calendar() -> int:
    """Run the Google Calendar MCP server's one-time browser auth.

    Writes the cached token to ~/.config/google-calendar-mcp/tokens.json; later runs reuse
    it. Requires the OAuth client JSON at ~/.google-calendar-mcp/gcp-oauth.keys.json.
    """
    _GCAL_DIR.mkdir(exist_ok=True)
    if not _GCAL_KEYS.exists():
        print(
            f"Missing {_GCAL_KEYS} — create a Google OAuth client first "
            "(see docs/google-calendar-mcp-setup.md).",
            file=sys.stderr,
        )
        return 1
    print("Launching Google Calendar OAuth (a browser window will open)…")
    env = {**os.environ, "GOOGLE_OAUTH_CREDENTIALS": str(_GCAL_KEYS)}
    return subprocess.call(["npx", "-y", "@cocal/google-calendar-mcp", "auth"], env=env)


def _cmd_atlassian() -> int:
    """Run the Atlassian remote-MCP OAuth flow via mcp-remote (opens a browser).

    Tokens are cached under ~/.mcp-auth, which docker-compose mounts into the container.
    Keep this process running until the browser flow completes and the token is written;
    Ctrl-C afterwards is fine.
    """
    _MCP_AUTH_DIR.mkdir(exist_ok=True)
    print("Launching Atlassian OAuth via mcp-remote (a browser window will open)…")
    print("Complete the login in your browser, then Ctrl-C once the token is saved.")
    return subprocess.call(["npx", "-y", "mcp-remote", _ATLASSIAN_MCP_URL])


def main() -> None:
    parser = argparse.ArgumentParser(prog="jarvis-auth", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Show which MCP servers have tokens configured")
    p_set = sub.add_parser("set", help="Write a token to .env")
    p_set.add_argument("key")
    p_set.add_argument("value")
    sub.add_parser("gmail", help="Run the one-time Gmail OAuth browser flow")
    sub.add_parser("calendar", help="Run the one-time Google Calendar OAuth browser flow")
    sub.add_parser("atlassian", help="Run the one-time Atlassian OAuth browser flow")

    args = parser.parse_args()
    if args.command == "status":
        sys.exit(_cmd_status())
    if args.command == "set":
        sys.exit(_cmd_set(args.key, args.value))
    if args.command == "gmail":
        sys.exit(_cmd_gmail())
    if args.command == "calendar":
        sys.exit(_cmd_calendar())
    if args.command == "atlassian":
        sys.exit(_cmd_atlassian())


if __name__ == "__main__":
    main()
