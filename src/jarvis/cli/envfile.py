"""Minimal .env reader/writer for the auth CLI.

Preserves comments and ordering; updates a key in place or appends it. Deliberately tiny
(no python-dotenv dependency) since the format we use is plain ``KEY=value`` lines.
"""

from __future__ import annotations

from pathlib import Path


def read_env(path: Path) -> dict[str, str]:
    """Parse KEY=value lines (ignoring comments/blanks) into a dict."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, val = stripped.partition("=")
        values[key.strip()] = val.strip()
    return values


def set_env(path: Path, key: str, value: str) -> None:
    """Set ``key`` to ``value`` in the .env file, updating in place or appending."""
    lines = path.read_text().splitlines() if path.exists() else []
    new_line = f"{key}={value}"
    for i, line in enumerate(lines):
        # Match an existing assignment (allow leading whitespace), skip comments.
        bare = line.lstrip()
        if not bare.startswith("#") and bare.split("=", 1)[0].strip() == key:
            lines[i] = new_line
            path.write_text("\n".join(lines) + "\n")
            return
    lines.append(new_line)
    path.write_text("\n".join(lines) + "\n")
