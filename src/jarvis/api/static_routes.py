"""Static SPA routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def register_static_routes(app: FastAPI, *, static_dir: str) -> None:
    static = Path(static_dir)
    assets = static / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/favicon.svg")
    async def favicon() -> FileResponse:
        """Vite emits public/ assets to the dist root, which isn't under /assets."""
        return FileResponse(str(static / "favicon.svg"))

    @app.get("/")
    async def dashboard() -> FileResponse:
        """Serve the built SPA shell; the app then loads /session + /view-model."""
        return FileResponse(str(static / "index.html"))
