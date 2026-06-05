"""Unified logging config.

One root handler with a consistent ``timestamp LEVEL name: message`` format. uvicorn,
alembic, and other libraries install their own handlers (uvicorn's ``INFO:     ...``
lines, alembic's ``INFO  [...]``); we strip those and force the loggers to propagate
to the root so every Python log line looks the same.

Note: external MCP subprocesses (slack/github/atlassian) write their own JSON/text to
stdout — those originate outside Python and are not affected by this config.
"""

from __future__ import annotations

import logging
from logging.config import dictConfig

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"

# Library loggers that ship their own handlers — clear them and let records propagate
# to the root so they pick up our single formatter.
_RESET_LOGGERS = (
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "alembic",
    "alembic.runtime.migration",
)


def configure_logging(level: str = "info") -> None:
    """Install a single root handler and normalize known library loggers."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"standard": {"format": _FORMAT, "datefmt": _DATEFMT}},
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {"handlers": ["default"], "level": log_level},
            # Empty handler list + propagate=True: these flow through root's formatter
            # instead of their own. handlers=[] also drops the duplicate handlers the
            # libraries would otherwise install.
            "loggers": {
                name: {"handlers": [], "level": log_level, "propagate": True}
                for name in _RESET_LOGGERS
            },
        }
    )
