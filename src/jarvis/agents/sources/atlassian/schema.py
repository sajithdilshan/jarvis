"""Atlassian (Jira + Confluence) agent result schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, model_validator


class AtlassianItem(BaseModel):
    type: Literal["jira_issue", "jira_mention", "confluence_page", "confluence_mention"]
    source: Literal["jira", "confluence"]
    key: str  # Jira issue key (e.g. PROJ-123) or Confluence page id
    title: str
    url: str
    requires_action: bool = False
    raw_data_id: str


class AtlassianSummary(BaseModel):
    items: list[AtlassianItem] = []
    issues_assigned: int = 0
    mentions: int = 0

    @model_validator(mode="after")
    def _derive_counts(self) -> "AtlassianSummary":
        # Counts are derived from the items, not trusted from the agent: issues_assigned is
        # the number of Jira issues, mentions is the number of *_mention items.
        self.issues_assigned = sum(1 for i in self.items if i.type == "jira_issue")
        self.mentions = sum(1 for i in self.items if i.type.endswith("_mention"))
        return self
