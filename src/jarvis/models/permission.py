"""Typed contracts for standing permissions and execution audit rows."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PermissionRecord(BaseModel):
    id: str
    description: str
    source: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    allowed_actions: list[str] = Field(default_factory=list)
    max_matches: int | None = None
    active: bool = True
    created_at: str | None = None
    created_via: str | None = None


class PermissionCreate(BaseModel):
    id: str
    description: str
    source: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    allowed_actions: list[str] = Field(default_factory=list)
    created_via: str | None = None
    max_matches: int | None = None


class PermissionUpdate(BaseModel):
    description: str
    source: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    allowed_actions: list[str] = Field(default_factory=list)
    max_matches: int | None = None


class PermissionExecutionAuditRow(BaseModel):
    permission_id: str
    permission_desc: str
    session_id: str
    source: str
    item_id: str
    tool: str
    status: str
    detail: str | None = None


def permission_record_from_row(row) -> PermissionRecord:
    return PermissionRecord(
        id=row.id,
        description=row.description,
        source=row.source,
        constraints=row.constraints or {},
        allowed_actions=list(row.allowed_actions or []),
        max_matches=row.max_matches,
        active=row.active,
        created_at=row.created_at.isoformat() if row.created_at else None,
        created_via=row.created_via,
    )


def iso_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
