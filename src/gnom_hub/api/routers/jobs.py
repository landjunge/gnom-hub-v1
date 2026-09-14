"""HTTP routes: jobs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from gnom_hub.hub import get_hub

router = APIRouter()


@router.get("/api/jobs")
def jobs_list(limit: int = Query(20, ge=1, le=50)) -> dict[str, Any]:
    jobs = get_hub().list_jobs(limit)
    running = sum(1 for j in jobs if j.get("status") == "running")
    busy = get_hub()._find_busy_job()
    return {
        "jobs": jobs,
        "count": len(jobs),
        "running": running,
        "busy": (
            {
                "id": busy.get("id"),
                "name": busy.get("name"),
                "stage": busy.get("stage"),
                "status": busy.get("status"),
                "cancel": bool(busy.get("cancel")),
                "started_at": busy.get("started_at") or "",
            }
            if busy
            else None
        ),
    }


@router.get("/api/jobs/busy")
def jobs_busy() -> dict[str, Any]:
    """Current pipeline occupant (if any) — for desk banner."""
    busy = get_hub()._find_busy_job()
    if not busy:
        return {"busy": False}
    return {
        "busy": True,
        "busy_job_id": busy.get("id"),
        "busy_name": busy.get("name"),
        "busy_stage": busy.get("stage"),
        "status": busy.get("status"),
        "cancel": bool(busy.get("cancel")),
        "started_at": busy.get("started_at") or "",
        "timeout_s": busy.get("timeout_s"),
    }


@router.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict[str, Any]:
    job = get_hub().get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="unknown job")
    return job


@router.post("/api/jobs/cancel-busy")
def job_cancel_busy() -> dict[str, Any]:
    """Cancel the job that currently holds the pipeline (if any)."""
    return get_hub().cancel_busy_job()


@router.post("/api/jobs/{job_id}/cancel")
def job_cancel(
    job_id: str,
    as_timeout: bool = Query(False, description="Mark as FEHLER timeout (poll deadline)"),
) -> dict[str, Any]:
    try:
        return get_hub().cancel_job(job_id, as_timeout=as_timeout)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
