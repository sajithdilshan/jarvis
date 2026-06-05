"""Gmail agent result schema."""

from __future__ import annotations

from pydantic import BaseModel, model_validator


class EmailItem(BaseModel):
    id: str
    sender: str  # display form,
    sender_email: str = ""  # bare email address
    subject: str
    snippet: str  # Gmail's short preview (~100 chars)
    body: str = ""  # full plain-text body — used for content-match permissions
    timestamp: str
    is_urgent: bool
    labels: list[str] = []
    raw_data_id: str
    url: str | None = None  # Gmail permalink, e.g. https://mail.google.com/mail/#all/<id>


class GmailSummary(BaseModel):
    emails: list[EmailItem] = []
    total_unread: int = 0
    has_urgent: bool = False

    @model_validator(mode="after")
    def _derive_counts(self) -> "GmailSummary":
        # Counts are derived from the items, not trusted from the agent: total_unread is
        # the number of emails returned, has_urgent is true iff any is flagged urgent.
        self.total_unread = len(self.emails)
        self.has_urgent = any(e.is_urgent for e in self.emails)
        return self
