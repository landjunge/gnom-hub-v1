"""HTTP routes: system."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from gnom_hub import __version__
from gnom_hub.api.models import (
    GodModeBody,
    PlanModeBody,
    SystemBody,
    TeamPresetBody,
    WorkerPresetBody,
)
from gnom_hub.hub import get_hub
from gnom_hub.stack import stack_snapshot

router = APIRouter()


@router.get("/api/health")
def health() -> dict[str, Any]:
    hub = get_hub()
    return {
        "status": "ok",
        "service": "gnom-hub-v1",
        "version": __version__,
        "telegram": hub.telegram.enabled,
        "telegram_running": hub.telegram.running,
        "llm": {
            "deepseek": hub.llm.has_provider("deepseek"),
            "ollama": hub.llm.has_provider("ollama"),
            "auth": (hub.llm.auth_snapshot() if hasattr(hub.llm, "auth_snapshot") else {}),
        },
        "stack": stack_snapshot(),
    }


@router.get("/api/system")
def system_get() -> dict[str, Any]:
    return get_hub().system_dict()


@router.post("/api/system")
def system_set(body: SystemBody) -> dict[str, Any]:
    return get_hub().set_system(body.model_dump(exclude_unset=True))


@router.get("/api/trace")
def trace(limit: int = Query(40, ge=1, le=100)) -> dict[str, Any]:
    hub = get_hub()
    return {"trace": list(hub.trace[-limit:]), "count": len(hub.trace)}


@router.get("/api/trace/export")
def trace_export(
    limit: int = Query(100, ge=1, le=100),
    fmt: str = Query("json"),
) -> dict[str, Any]:
    """Downloadable light trace (json or md)."""
    return get_hub().export_trace(limit=limit, fmt=fmt)


@router.post("/api/trace/clear")
def trace_clear() -> dict[str, Any]:
    return get_hub().clear_trace()


@router.post("/api/checkpoint/save")
def checkpoint_save() -> dict[str, Any]:
    return get_hub().save_checkpoint()


@router.post("/api/checkpoint/load")
def checkpoint_load() -> dict[str, Any]:
    try:
        return get_hub().load_checkpoint()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/api/clean")
def clean_state() -> dict[str, Any]:
    """One-click clean: HOT + temp workspace + pipeline; WARM kept."""
    return get_hub().clean_state()


@router.post("/api/backup")
def backup() -> dict[str, Any]:
    return get_hub().create_backup()


@router.get("/api/backups")
def backups_list() -> dict[str, Any]:
    return {"backups": get_hub().list_backups()}


@router.get("/api/backups/{name}/download")
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


@router.delete("/api/backups/{name}")
def backups_delete(name: str) -> dict[str, Any]:
    try:
        return get_hub().delete_backup(name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/api/backups/{name}/restore")
def backups_restore(
    name: str,
    archive_current: bool = Query(True),
    load_checkpoint: bool = Query(True),
) -> dict[str, Any]:
    """Restore HOT/WARM/agents from a backup zip."""
    try:
        return get_hub().restore_backup(
            name,
            archive_current=archive_current,
            load_checkpoint=load_checkpoint,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/api/worker-presets")
def worker_presets_list() -> dict[str, Any]:
    return {"presets": get_hub().list_worker_presets()}


@router.post("/api/worker-presets")
def worker_presets_save(body: WorkerPresetBody) -> dict[str, Any]:
    try:
        return get_hub().save_worker_preset(body.name, body.agent_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/api/worker-presets/apply")
def worker_presets_apply(body: WorkerPresetBody) -> dict[str, Any]:
    try:
        return get_hub().apply_worker_preset(body.name, body.agent_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/api/worker-presets/delete")
def worker_presets_delete(body: WorkerPresetBody) -> dict[str, Any]:
    return get_hub().delete_worker_preset(body.name)


@router.get("/api/team-presets")
def team_presets_list() -> dict[str, Any]:
    hub = get_hub()
    return {
        "presets": hub.list_team_presets(),
        "plan_mode": hub.plan_mode,
        "plan_modes": list(hub.PLAN_MODES),
    }


@router.post("/api/team-presets")
def team_presets_save(body: TeamPresetBody) -> dict[str, Any]:
    return get_hub().save_team_preset(body.name)


@router.post("/api/team-presets/apply")
def team_presets_apply(body: TeamPresetBody) -> dict[str, Any]:
    try:
        return get_hub().apply_team_preset(body.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/api/team-presets/delete")
def team_presets_delete(body: TeamPresetBody) -> dict[str, Any]:
    return get_hub().delete_team_preset(body.name)


@router.post("/api/plan-mode")
def plan_mode_set(body: PlanModeBody) -> dict[str, Any]:
    try:
        return get_hub().set_plan_mode(body.plan_mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/api/usage")
def usage_get() -> dict[str, Any]:
    return get_hub().usage_dict()


@router.post("/api/usage/reset")
def usage_reset() -> dict[str, Any]:
    return get_hub().reset_usage()


@router.post("/api/save")
def save() -> dict[str, Any]:
    return get_hub().save()


@router.post("/api/reset")
def reset(
    clear_warm: bool = Query(False),
    archive: bool = Query(True),
) -> dict[str, Any]:
    return get_hub().reset_session(keep_agents=True, clear_warm=clear_warm, archive=archive)


@router.get("/api/help")
def help_() -> dict[str, Any]:
    return get_hub().help_text()


@router.post("/api/god-mode")
def god_mode(body: GodModeBody) -> dict[str, Any]:
    return get_hub().set_god_mode(body.enabled, reason="user", assignment_id=body.assignment_id)


@router.get("/api/god-mode")
def god_mode_get() -> dict[str, Any]:
    return get_hub().god_mode.snapshot()
