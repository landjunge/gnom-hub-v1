"""FastAPI app: static UI + JSON API for hub control."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
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


class WarmFactBody(BaseModel):
    text: str = Field(min_length=1)


class WorkspaceWriteBody(BaseModel):
    zone: str = "temp"
    name: str = Field(min_length=1)
    content: str = ""


class TelegramInBody(BaseModel):
    text: str = Field(min_length=1)
    chat_id: int | None = None


def create_app() -> FastAPI:
    app = FastAPI(title="Gnom-Hub v1", version="0.2.0")

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        hub = get_hub()
        return {
            "status": "ok",
            "service": "gnom-hub-v1",
            "telegram": hub.telegram.enabled,
            "telegram_running": hub.telegram.running,
        }

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

    @app.post("/api/reset")
    def reset(clear_warm: bool = Query(False)) -> dict[str, Any]:
        return get_hub().reset_session(keep_agents=True, clear_warm=clear_warm)

    @app.get("/api/help")
    def help_() -> dict[str, Any]:
        return get_hub().help_text()

    @app.get("/api/canvas")
    def canvas() -> dict[str, Any]:
        return get_hub().canvas()

    @app.get("/api/memory")
    def memory() -> dict[str, Any]:
        return get_hub().memory_dict()

    @app.post("/api/memory/warm")
    def warm_add(body: WarmFactBody) -> dict[str, Any]:
        ok = get_hub().warm.add_fact(body.text.strip())
        return {"ok": ok, "warm_facts": get_hub().warm.recent_facts(12)}

    @app.get("/api/workspace")
    def workspace() -> dict[str, Any]:
        return get_hub().workspace.snapshot()

    @app.post("/api/workspace/write")
    def workspace_write(body: WorkspaceWriteBody) -> dict[str, Any]:
        try:
            path = get_hub().workspace.write_text(body.zone, body.name, body.content)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return {"ok": True, "path": str(path), "workspace": get_hub().workspace.snapshot()}

    @app.post("/api/workspace/promote/{name}")
    def workspace_promote(name: str) -> dict[str, Any]:
        try:
            path = get_hub().workspace.promote(name)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return {"ok": True, "path": str(path), "workspace": get_hub().workspace.snapshot()}

    @app.post("/api/telegram/start")
    def telegram_start() -> dict[str, Any]:
        return get_hub().telegram_start()

    @app.post("/api/telegram/stop")
    def telegram_stop() -> dict[str, Any]:
        return get_hub().telegram_stop()

    @app.post("/api/telegram/inbound")
    def telegram_inbound(body: TelegramInBody) -> dict[str, Any]:
        """Test hook / webhook-style without Telegram servers."""
        return get_hub().telegram_inbound(body.text, body.chat_id)

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
