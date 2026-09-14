"""FastAPI app: static UI + JSON API for hub control."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from gnom_hub import __version__
from gnom_hub.api.routers import (
    agents,
    chat,
    execute,
    jobs,
    memory,
    rest,
    skills,
    system,
    tools,
    workspace,
)

STATIC_DIR = Path(__file__).resolve().parents[1] / "ui" / "static"


def create_app() -> FastAPI:
    app = FastAPI(title="Gnom-Hub v1", version=__version__)
    app.include_router(system.router)
    app.include_router(rest.router)
    app.include_router(agents.router)
    app.include_router(execute.router)
    app.include_router(chat.router)
    app.include_router(jobs.router)
    app.include_router(memory.router)
    app.include_router(workspace.router)
    app.include_router(tools.router)
    app.include_router(skills.router)

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app


app = create_app()
