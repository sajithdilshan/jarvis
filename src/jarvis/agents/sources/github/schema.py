"""GitHub agent result schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, model_validator


class GithubNotification(BaseModel):
    type: Literal["pr_review", "issue", "mention", "ci_failure", "pr_comment", "pr_approval"]
    repo: str
    title: str
    url: str
    requires_action: bool = False
    raw_data_id: str


class GithubSummary(BaseModel):
    notifications: list[GithubNotification] = []
    prs_needing_review: int = 0
    mentions: int = 0

    @model_validator(mode="after")
    def _derive_counts(self) -> "GithubSummary":
        # Counts are derived from the items, not trusted from the agent: prs_needing_review
        # is the number of review-request items, mentions is the number of mention items.
        self.prs_needing_review = sum(1 for n in self.notifications if n.type == "pr_review")
        self.mentions = sum(1 for n in self.notifications if n.type == "mention")
        return self
