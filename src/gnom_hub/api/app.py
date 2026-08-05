"""FastAPI app: static UI + JSON API for hub control."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from gnom_hub.hub import get_hub

STATIC_DIR = Path(__file__).resolve().parents[1] / "ui" / "static"


class ChatBody(BaseModel):
    text: str = Field(min_length=1)


class ClarifyBody(BaseModel):
    option: str = Field(min_length=1)


class FlexBody(BaseModel):
    preset: str = Field(min_length=1)


class AgentLlmBody(BaseModel):
    model: str | None = None
    api_key: str | None = None


def create_app() -> FastAPI:
    app = FastAPI(title="Gnom-Hub v1", version="0.1.0")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "gnom-hub-v1"}

    @app.get("/api/state")
    def state() -> dict[str, Any]:
        return get_hub().snapshot()

    @app.get("/api/agents")
    def agents() -> dict[str, Any]:
        hub = get_hub()
        return {"agents": [hub._agent_dict(a) for a in hub.agents.list_agents()]}

    @app.post("/api/agents/{agent_id}/toggle")
    def toggle(agent_id: str) -> dict[str, Any]:
        try:
            return get_hub().toggle_agent(agent_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.post("/api/agents/flex/preset")
    def flex_preset(body: FlexBody) -> dict[str, Any]:
        try:
            return get_hub().set_flex_preset(body.preset)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.post("/api/agents/{agent_id}/llm")
    def agent_llm(agent_id: str, body: AgentLlmBody) -> dict[str, Any]:
        try:
            return get_hub().set_agent_llm(agent_id, model=body.model, api_key=body.api_key)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.post("/api/chat")
    def chat(body: ChatBody) -> dict[str, Any]:
        return get_hub().chat(body.text.strip())

    @app.post("/api/clarify")
    def clarify(body: ClarifyBody) -> dict[str, Any]:
        try:
            return get_hub().clarify(body.option.strip())
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.post("/api/save")
    def save() -> dict[str, Any]:
        return get_hub().save()

    @app.get("/api/tooltips")
    def tooltips(lang: str = "en") -> dict[str, Any]:
        return get_hub().tooltips(lang)

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app


app = create_app()
