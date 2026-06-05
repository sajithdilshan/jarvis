"""Slack agent result schema."""

from __future__ import annotations

from pydantic import BaseModel, model_validator


class SlackMessage(BaseModel):
    channel: str
    author: str
    content: str
    timestamp: str
    is_mention: bool = False
    thread_id: str | None = None
    raw_data_id: str
    url: str | None = None  # Slack permalink to the message/thread


class SlackSummary(BaseModel):
    messages: list[SlackMessage] = []
    channels_with_activity: list[str] = []
    direct_messages: int = 0

    @model_validator(mode="after")
    def _derive_counts(self) -> "SlackSummary":
        # Derived from the messages, not trusted from the agent: channels_with_activity is
        # the sorted distinct channels; direct_messages counts DMs/group-DMs (channel names
        # starting with "@" — "#" channels are not DMs).
        self.channels_with_activity = sorted({m.channel for m in self.messages})
        self.direct_messages = sum(1 for m in self.messages if m.channel.startswith("@"))
        return self
