"""HTTP routes: chat."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from gnom_hub.api.models import ChatBody, ClarifyBody
from gnom_hub.hub import get_hub

router = APIRouter()


@router.post("/api/chat")
def chat(
    body: ChatBody,
    sync: bool = Query(False),
    full: bool = Query(False),
) -> dict[str, Any]:
    """Default: brainstorm turn only. full=1 runs whole pipeline (tests/Telegram)."""
    text = body.text.strip()
    if sync:
        # Sync path also blocks on lock — refuse if another job holds it
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
        try:
            return get_hub().chat_sync(text, full=full, target=body.target)
        except ValueError as e:
            if str(e).startswith("invalid send target"):
                raise HTTPException(status_code=400, detail=str(e)) from e
            raise
    try:
        out = get_hub().chat_async(text, full=full, target=body.target)
    except ValueError as e:
        if str(e).startswith("invalid send target"):
            raise HTTPException(status_code=400, detail=str(e)) from e
        raise
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


@router.post("/api/clarify")
def clarify(body: ClarifyBody, sync: bool = Query(False)) -> dict[str, Any]:
    try:
        if sync:
            return get_hub().clarify(body.option.strip())
        return get_hub().clarify_async(body.option.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/api/clarify/resume")
def clarify_resume(index: int = Query(-1)) -> dict[str, Any]:
    """Resume a deferred (Later) clarification as active Box-1 question."""
    try:
        return get_hub().resume_deferred_clarify(index)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
