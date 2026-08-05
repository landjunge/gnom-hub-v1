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


class AgentTuneBody(BaseModel):
    model: str | None = None
    api_key: str | None = None
    system_prompt: str | None = None
    tts: bool | None = None
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None


class SystemBody(BaseModel):
    free_only: bool | None = None
    max_budget_usd: float | None = None
    default_model: str | None = None
    ui_lang: str | None = None
    auto_pack_after_execute: bool | None = None
    pack_max: int | None = None


class WorkerPresetBody(BaseModel):
    name: str = Field(min_length=1)
    agent_id: str = "worker1"


class WarmFactBody(BaseModel):
    text: str = Field(min_length=1)


class WorkspaceWriteBody(BaseModel):
    zone: str = "temp"
    name: str = Field(min_length=1)
    content: str = ""


class TelegramInBody(BaseModel):
    text: str = Field(min_length=1)
    chat_id: int | None = None


class GodModeBody(BaseModel):
    enabled: bool
    reason: str = "api"


class VectorAddBody(BaseModel):
    text: str = Field(min_length=1)
    meta: dict[str, Any] | None = None


class VectorSearchBody(BaseModel):
    query: str = Field(min_length=1)
    limit: int = 5


class ToolCallBody(BaseModel):
    name: str = Field(min_length=1)
    arguments: dict[str, Any] | None = None


class ColdLabelBody(BaseModel):
    label: str = ""


class SessionPackBody(BaseModel):
    pack: dict[str, Any]
    include_warm: bool = True
    include_agents: bool = True
    store: bool = False


class PackRenameBody(BaseModel):
    label: str = Field(min_length=1, max_length=80)


class ReexecuteBody(BaseModel):
    user_text: str = ""
    brainstorm_notes: str = ""
    brainstorm_turns: list[dict[str, Any]] | None = None


class ActionClickBody(BaseModel):
    x: int
    y: int


class ShellBody(BaseModel):
    cmd: str = Field(min_length=1, max_length=200)


def create_app() -> FastAPI:
    app = FastAPI(title="Gnom-Hub v1", version="2.3.0")

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        hub = get_hub()
        return {
            "status": "ok",
            "service": "gnom-hub-v1",
            "version": "2.3.0",
            "telegram": hub.telegram.enabled,
            "telegram_running": hub.telegram.running,
            "llm": {
                "deepseek": hub.llm.has_provider("deepseek"),
                "ollama": hub.llm.has_provider("ollama"),
            },
        }

    @app.get("/api/ollama/models")
    def ollama_models() -> dict[str, Any]:
        hub = get_hub()
        models = hub.llm.list_ollama_models()
        return {
            "ok": hub.llm.has_provider("ollama"),
            "host": hub.llm.providers_snapshot().get("ollama_host"),
            "models": models,
        }

    @app.get("/api/export/last")
    def export_last() -> dict[str, Any]:
        """Export last brainstorm + worker outputs for download."""
        hub = get_hub()
        st = hub.pipeline.state
        parts = [
            "# Gnom-Hub export",
            f"stage={st.stage.value}",
            f"user={st.user_text}",
            "",
            "## Brainstorm",
            st.brainstorm_notes or "(none)",
            "",
            "## Requirements",
            "\n".join(f"- {r}" for r in st.distilled_requirements) or "(none)",
            "",
            "## Flex",
            st.flex_notes or "(none)",
            "",
            "## Quality",
            st.quality_notes or "(none)",
            "",
        ]
        for out in st.worker_outputs or []:
            parts.append(f"## {out.get('name') or out.get('worker')}")
            parts.append(f"Task: {out.get('task') or ''}")
            parts.append(str(out.get("result") or ""))
            parts.append("")
        text = "\n".join(parts)
        return {
            "ok": True,
            "filename": "gnom-hub-export.md",
            "content": text,
            "chars": len(text),
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

    @app.post("/api/agents/enable-all")
    def enable_all_agents() -> dict[str, Any]:
        hub = get_hub()
        hub.agents.enable_all()
        return {
            "ok": True,
            "agents": [hub._agent_dict(a) for a in hub.agents.list_agents()],
        }

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

    @app.post("/api/agents/{agent_id}/tune")
    def agent_tune(agent_id: str, body: AgentTuneBody) -> dict[str, Any]:
        try:
            return get_hub().set_agent_tune(agent_id, body.model_dump(exclude_unset=True))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.get("/api/system")
    def system_get() -> dict[str, Any]:
        return get_hub().system_dict()

    @app.post("/api/system")
    def system_set(body: SystemBody) -> dict[str, Any]:
        return get_hub().set_system(body.model_dump(exclude_unset=True))

    @app.get("/api/trace")
    def trace(limit: int = Query(40, ge=1, le=100)) -> dict[str, Any]:
        hub = get_hub()
        return {"trace": list(hub.trace[-limit:]), "count": len(hub.trace)}

    @app.post("/api/checkpoint/save")
    def checkpoint_save() -> dict[str, Any]:
        return get_hub().save_checkpoint()

    @app.post("/api/checkpoint/load")
    def checkpoint_load() -> dict[str, Any]:
        try:
            return get_hub().load_checkpoint()
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    @app.post("/api/clean")
    def clean_state() -> dict[str, Any]:
        """One-click clean: HOT + temp workspace + pipeline; WARM kept."""
        return get_hub().clean_state()

    @app.post("/api/backup")
    def backup() -> dict[str, Any]:
        return get_hub().create_backup()

    @app.get("/api/session/pack")
    def session_pack_export(
        persist: bool = Query(True),
        label: str | None = Query(None),
    ) -> dict[str, Any]:
        """Downloadable portable session pack (HOT + WARM + agents + pipeline)."""
        return get_hub().export_session_pack(label=label, persist=persist)

    @app.post("/api/session/pack")
    def session_pack_import(body: SessionPackBody) -> dict[str, Any]:
        try:
            return get_hub().import_session_pack(
                body.pack,
                include_warm=body.include_warm,
                include_agents=body.include_agents,
                store=body.store,
            )
        except (ValueError, TypeError) as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.get("/api/session/packs")
    def session_packs_list() -> dict[str, Any]:
        return {"packs": get_hub().list_session_packs()}

    @app.get("/api/session/packs/{name}")
    def session_pack_get(name: str) -> dict[str, Any]:
        try:
            return get_hub().load_session_pack_file(name)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    @app.get("/api/session/packs/{name}/download")
    def session_pack_download(name: str) -> FileResponse:
        """Download a stored pack file (USB copy)."""
        try:
            path = get_hub()._pack_path(name)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return FileResponse(
            path,
            media_type="application/json",
            filename=path.name,
        )

    @app.post("/api/session/packs/{name}/import")
    def session_pack_import_named(
        name: str,
        include_warm: bool = Query(True),
        include_agents: bool = Query(True),
    ) -> dict[str, Any]:
        try:
            return get_hub().import_session_pack_file(
                name, include_warm=include_warm, include_agents=include_agents
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except TypeError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.patch("/api/session/packs/{name}")
    def session_pack_rename(name: str, body: PackRenameBody) -> dict[str, Any]:
        try:
            return get_hub().rename_session_pack(name, body.label)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except TypeError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    @app.delete("/api/session/packs/{name}")
    def session_pack_delete(name: str) -> dict[str, Any]:
        try:
            return get_hub().delete_session_pack(name)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    @app.post("/api/reexecute")
    def reexecute(body: ReexecuteBody, sync: bool = Query(False)) -> dict[str, Any]:
        """Restore brainstorm context from history, then run Execute."""
        try:
            get_hub().restore_for_reexecute(
                user_text=body.user_text,
                brainstorm_notes=body.brainstorm_notes,
                brainstorm_turns=body.brainstorm_turns,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if sync:
            return get_hub().execute_sync()
        return get_hub().execute_async()

    @app.get("/api/backups")
    def backups_list() -> dict[str, Any]:
        return {"backups": get_hub().list_backups()}

    @app.get("/api/backups/{name}/download")
    def backups_download(name: str) -> FileResponse:
        try:
            path = get_hub().backup_path(name)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return FileResponse(
            path,
            media_type="application/zip",
            filename=path.name,
        )

    @app.delete("/api/backups/{name}")
    def backups_delete(name: str) -> dict[str, Any]:
        try:
            return get_hub().delete_backup(name)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    @app.get("/api/worker-presets")
    def worker_presets_list() -> dict[str, Any]:
        return {"presets": get_hub().list_worker_presets()}

    @app.post("/api/worker-presets")
    def worker_presets_save(body: WorkerPresetBody) -> dict[str, Any]:
        try:
            return get_hub().save_worker_preset(body.name, body.agent_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.post("/api/worker-presets/apply")
    def worker_presets_apply(body: WorkerPresetBody) -> dict[str, Any]:
        try:
            return get_hub().apply_worker_preset(body.name, body.agent_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.post("/api/worker-presets/delete")
    def worker_presets_delete(body: WorkerPresetBody) -> dict[str, Any]:
        return get_hub().delete_worker_preset(body.name)

    @app.post("/api/chat")
    def chat(
        body: ChatBody,
        sync: bool = Query(False),
        full: bool = Query(False),
    ) -> dict[str, Any]:
        """Default: brainstorm turn only. full=1 runs whole pipeline (tests/Telegram)."""
        text = body.text.strip()
        if sync:
            return get_hub().chat_sync(text, full=full)
        return get_hub().chat_async(text, full=full)

    @app.post("/api/execute")
    def execute(sync: bool = Query(False)) -> dict[str, Any]:
        """Run distill → workers from accumulated brainstorm."""
        if sync:
            return get_hub().execute_sync()
        return get_hub().execute_async()

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: str) -> dict[str, Any]:
        job = get_hub().get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="unknown job")
        return job

    @app.post("/api/jobs/{job_id}/cancel")
    def job_cancel(job_id: str) -> dict[str, Any]:
        try:
            return get_hub().cancel_job(job_id)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    @app.post("/api/clarify")
    def clarify(body: ClarifyBody, sync: bool = Query(False)) -> dict[str, Any]:
        try:
            if sync:
                return get_hub().clarify(body.option.strip())
            return get_hub().clarify_async(body.option.strip())
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.post("/api/save")
    def save() -> dict[str, Any]:
        return get_hub().save()

    @app.post("/api/reset")
    def reset(
        clear_warm: bool = Query(False),
        archive: bool = Query(True),
    ) -> dict[str, Any]:
        return get_hub().reset_session(keep_agents=True, clear_warm=clear_warm, archive=archive)

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

    @app.get("/api/workspace/file")
    def workspace_file(
        zone: str = Query("temp"),
        name: str = Query(..., min_length=1),
    ) -> dict[str, Any]:
        try:
            content = get_hub().workspace.read_text(zone, name)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return {"ok": True, "zone": zone, "name": name, "content": content}

    @app.post("/api/workspace/clear-temp")
    def workspace_clear_temp() -> dict[str, Any]:
        n = get_hub().workspace.clear_temp()
        return {"ok": True, "removed": n, "workspace": get_hub().workspace.snapshot()}

    @app.post("/api/workspace/delete")
    def workspace_delete(
        zone: str = Query("temp"),
        name: str = Query(..., min_length=1),
    ) -> dict[str, Any]:
        try:
            ok = get_hub().workspace.delete(zone, name)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if not ok:
            raise HTTPException(status_code=404, detail="not found")
        return {"ok": True, "workspace": get_hub().workspace.snapshot()}

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

    # ── COLD / Vector / God-Mode / Computer-Use / Plugins ──

    @app.post("/api/cold/archive")
    def cold_archive(body: ColdLabelBody | None = None) -> dict[str, Any]:
        label = body.label if body else ""
        return get_hub().archive_cold(label=label or "")

    @app.get("/api/cold")
    def cold_list() -> dict[str, Any]:
        return {"archives": get_hub().cold.list_archives()}

    @app.get("/api/cold/{archive_id}")
    def cold_get(archive_id: str) -> dict[str, Any]:
        data = get_hub().cold.get(archive_id)
        if not data:
            raise HTTPException(status_code=404, detail="archive not found")
        return data

    @app.post("/api/vector/add")
    def vector_add(body: VectorAddBody) -> dict[str, Any]:
        doc_id = get_hub().vectors.add(body.text, meta=body.meta)
        return {"ok": True, "id": doc_id, "count": get_hub().vectors.count()}

    @app.post("/api/vector/search")
    def vector_search(body: VectorSearchBody) -> dict[str, Any]:
        hits = get_hub().vectors.search(body.query, limit=body.limit)
        return {"hits": hits}

    @app.post("/api/god-mode")
    def god_mode(body: GodModeBody) -> dict[str, Any]:
        return get_hub().set_god_mode(body.enabled, reason=body.reason)

    @app.get("/api/god-mode")
    def god_mode_get() -> dict[str, Any]:
        return get_hub().god_mode.snapshot()

    @app.post("/api/computer-use/inspect")
    def computer_inspect() -> dict[str, Any]:
        return get_hub().computer.inspect_screen()

    @app.post("/api/computer-use/click")
    def computer_click(body: ActionClickBody) -> dict[str, Any]:
        r = get_hub().computer.action.click(body.x, body.y)
        return {"ok": r.ok, "dry_run": r.dry_run, "detail": r.detail}

    @app.post("/api/computer-use/shell")
    def computer_shell(body: ShellBody) -> dict[str, Any]:
        r = get_hub().computer.action.run_shell(body.cmd)
        return {
            "ok": r.ok,
            "dry_run": r.dry_run,
            "detail": r.detail,
            "stdout": r.stdout,
            "stderr": r.stderr,
        }

    @app.get("/api/plugins")
    def plugins() -> dict[str, Any]:
        hub = get_hub()
        return {"plugins": hub.plugin_list, "tools": hub.tools.list_tools()}

    @app.get("/api/mcp/tools")
    def mcp_tools() -> dict[str, Any]:
        return get_hub().tools.mcp_manifest()

    @app.post("/api/tools/call")
    def tools_call(body: ToolCallBody) -> dict[str, Any]:
        try:
            result = get_hub().tools.call(body.name, body.arguments)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return {"ok": True, "result": result}

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
