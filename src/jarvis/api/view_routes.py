"""View-model and briefing routes."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from jarvis.services.briefing_service import BriefingService
from jarvis.services.ui_service import UIService


class ResolveRequest(BaseModel):
    region: str = "feed"
    node_id: str


def register_view_routes(
    app: FastAPI,
    *,
    ui_service: UIService,
    briefing_service: BriefingService,
) -> None:
    @app.post("/resolve")
    async def resolve(request: ResolveRequest) -> dict:
        """User dismissed a card — remove it from the dashboard."""
        await ui_service.resolve_node(request.region, request.node_id)
        return {"ok": True}

    @app.get("/briefing-summary")
    async def briefing_summary() -> dict:
        """Daily summary for the calm empty state."""
        return {"resolved_today": await briefing_service.count_resolved_today()}

    @app.get("/view-model")
    async def latest_view_model() -> dict:
        """First-paint state: the canonical dashboard ViewModel."""
        return await ui_service.get_view_model()
