"""HTTP routes: workspace."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from gnom_hub.api.models import KeepSelectedBody, WorkspaceWriteBody
from gnom_hub.hub import get_hub

router = APIRouter()


@router.get("/api/workspace")
def workspace() -> dict[str, Any]:
    return get_hub().workspace.snapshot()


@router.post("/api/workspace/export")
def workspace_export(zone: str = Query("all")) -> dict[str, Any]:
    """Create zip of temp/perm/all under data/workspace/exports/."""
    try:
        return get_hub().export_workspace_zip(zone)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/api/workspace/exports/{name}")
def workspace_export_download(name: str) -> FileResponse:
    try:
        path = get_hub().workspace_export_path(name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return FileResponse(
        path,
        media_type="application/zip",
        filename=path.name,
    )


@router.post("/api/workspace/write")
def workspace_write(body: WorkspaceWriteBody) -> dict[str, Any]:
    try:
        path = get_hub().workspace.write_text(body.zone, body.name, body.content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "path": str(path), "workspace": get_hub().workspace.snapshot()}


@router.post("/api/workspace/promote/{name}")
def workspace_promote(name: str) -> dict[str, Any]:
    try:
        path = get_hub().workspace.promote(name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"ok": True, "path": str(path), "workspace": get_hub().workspace.snapshot()}


@router.post("/api/workspace/select/{name}")
def workspace_select(
    name: str,
    zone: str = Query("temp"),
) -> dict[str, Any]:
    """Copy ONE chosen HTML into personal WS selected/ (not bulk)."""
    try:
        path = get_hub().workspace.copy_to_selected(name, zone=zone)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {
        "ok": True,
        "path": str(path),
        "name": path.name,
        "workspace": get_hub().workspace.snapshot(),
    }


@router.post("/api/workspace/keep")
def workspace_keep(body: KeepSelectedBody) -> dict[str, Any]:
    """
    Behalten: HTML into personal WS selected/, other text into hub perm/.
    Never silent overwrite; verify read-back before success.
    """
    try:
        return get_hub().keep_result_to_personal_ws(
            body.content,
            name=body.name,
            worker=body.worker,
            overwrite=body.overwrite,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/api/workspace/file")
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


@router.post("/api/workspace/clear-temp")
def workspace_clear_temp() -> dict[str, Any]:
    n = get_hub().workspace.clear_temp()
    return {"ok": True, "removed": n, "workspace": get_hub().workspace.snapshot()}


@router.post("/api/workspace/delete")
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
