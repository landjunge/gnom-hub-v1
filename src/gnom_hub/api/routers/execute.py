"""HTTP routes: execute."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from gnom_hub.api.models import ReexecuteBody
from gnom_hub.hub import get_hub

router = APIRouter()


@router.post("/api/reexecute")
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


@router.post("/api/execute")
def execute(sync: bool = Query(False)) -> dict[str, Any]:
    """Run distill → workers from accumulated brainstorm."""
    if sync:
        busy = get_hub()._find_busy_job()
        if busy is not None:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": (
                        f"Pipeline busy (job {busy.get('id')} @ {busy.get('stage')}). "
                        "Cancel it first."
                    ),
                    "busy": True,
                    "busy_job_id": busy.get("id"),
                    "busy_stage": busy.get("stage"),
                    "busy_name": busy.get("name"),
                    "hint": "Cancel the running job then retry.",
                },
            )
        return get_hub().execute_sync()
    out = get_hub().execute_async()
    if out.get("busy") or out.get("status") == "busy":
        raise HTTPException(
            status_code=409,
            detail={
                "message": out.get("error") or out.get("message") or "Pipeline busy",
                "busy": True,
                "busy_job_id": out.get("busy_job_id"),
                "busy_stage": out.get("busy_stage"),
                "busy_name": out.get("busy_name"),
                "hint": "Cancel the running job (Esc / Cancel) then retry.",
            },
        )
    return out


@router.post("/api/workers/{worker_id}/rerun")
def worker_rerun(worker_id: str, sync: bool = Query(False)) -> dict[str, Any]:
    """Re-run a single worker (worker1–worker4) using its last task."""
    wid = worker_id.strip().lower()
    if wid not in ("worker1", "worker2", "worker3", "worker4"):
        raise HTTPException(status_code=400, detail="worker_id must be worker1–worker4")
    if sync:
        return get_hub().rerun_worker_sync(wid)
    return get_hub().rerun_worker_async(wid)
