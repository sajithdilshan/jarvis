"""UIService — notifies the WebSocket relay of feed changes and streams chat tokens.

Everything goes out over Postgres ``NOTIFY`` on a per-channel basis: the relay
(api/websocket.py) ``LISTEN``s and forwards each envelope to the browser verbatim.

The feed itself is never streamed. ``briefing_log`` is the source of truth: when it
changes we emit a tiny ``{"type": "feed_refresh"}`` ping and the client refetches
``/view-model``. So every envelope on the wire (feed_refresh, chat_token, progress)
is small — well under ``NOTIFY``'s 8000-byte cap, no spill buffer needed.
"""

from __future__ import annotations

import json

from jarvis.db.repositories.briefing_log_repo import BriefingLogRepo
from jarvis.db.repositories.ui_repo import UIRepo
from jarvis.models.agent_io import BriefingEntry
from jarvis.models.briefing import BriefingLogRecord
from jarvis.models.view_model import briefing_entry_node

# Scheduled runs have no open user socket; they stream to this shared channel that every
# browser also subscribes to, so background refreshes reach all connected tabs.
DEFAULT_CHANNEL = "default"

# Feed nodes render high-priority first (matches publish_briefing's emit order).
_PRIORITY_ORDER = {"high": 0, "normal": 1, "low": 2}


class UIService:
    def __init__(self, repo: UIRepo, briefing_repo: BriefingLogRepo):
        self._repo = repo
        self._briefing = briefing_repo

    @staticmethod
    def channel_name(channel: str) -> str:
        return f"jarvis_session_{channel}"

    async def _notify(self, channel: str, envelope: dict) -> None:
        """NOTIFY the channel with a small envelope (all wire envelopes are sub-cap)."""
        await self._repo.notify(self.channel_name(channel), json.dumps(envelope))

    async def publish_feed_refresh(self, channel: str = DEFAULT_CHANNEL) -> None:
        """Tell listening tabs the feed changed; they refetch /view-model and redraw.

        Defaults to the shared channel so a scheduled rebuild reaches every tab; pass a
        session channel for an action that should only nudge the originating session."""
        await self._notify(channel, {"type": "feed_refresh"})

    # --- ViewModel (rebuilt from briefing_log; no separate presentation store) ---

    async def get_view_model(self) -> dict:
        """The current dashboard ViewModel for first paint / new tabs.

        Rebuilt straight from the unresolved briefing_log — that table is the single
        source of truth, so a reload always reflects exactly what /resolve has dropped.
        Node mapping + sort match publish_briefing so live patches and first paint agree.
        """
        rows: list[BriefingLogRecord] = await self._briefing.unresolved_full()
        rows.sort(key=lambda r: _PRIORITY_ORDER.get(r.priority, 1))
        feed = [
            briefing_entry_node(BriefingEntry.model_validate(row.model_dump())).model_dump()
            for row in rows
        ]
        return {"regions": {"feed": feed}}

    async def resolve_node(self, region: str, node_id: str) -> None:
        """User dismissed an entry: mark resolved in briefing_log + redraw all tabs.

        Pure presentation action — marks resolved_at (so the next /view-model rebuild
        omits it), then broadcasts feed_refresh so open tabs refetch and drop it.
        """
        # Mark resolved first so the refresh-driven refetch already excludes it.
        await self._briefing.mark_resolved(node_id, only_unresolved=True)
        await self.publish_feed_refresh()

    async def stream_chat_token(self, channel: str, msg_id: str, delta: str) -> None:
        """Append one streaming chat token to the active assistant message."""
        await self._notify(channel, {"type": "chat_token", "msg_id": msg_id, "delta": delta})

    @staticmethod
    def intent_to_prompt(intent: str, args: dict | None) -> str:
        """Turn a user intent into a prompt for the main agent.

        Chat is the only channel to the agent — `/agent/invoke` is reached solely by chat
        submissions. Other intents are handled client-side (links, resolve) and never get
        here; we still degrade gracefully if one arrives.
        """
        args = args or {}
        if intent == "chat":
            return args.get("message", "")
        detail = ", ".join(f"{k}={v}" for k, v in args.items())
        return f"User action '{intent}'" + (f" ({detail})" if detail else "")
