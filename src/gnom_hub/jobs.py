"""Async job runner + job registry (extracted from Hub — pure move)."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any


class JobsMixin:
    """Mixin: expects Hub pipeline, bus, snapshot, cancel_check wiring."""

    def _start_job(self, name: str, runner: Any) -> dict[str, Any]:

        if not hasattr(self, "_jobs"):
            self._jobs: dict[str, dict[str, Any]] = {}
        lock = self._pipeline_lock_obj()

        job_id = uuid.uuid4().hex[:12]
        job: dict[str, Any] = {
            "id": job_id,
            "name": name,
            "status": "running",
            "stage": "queued",
            "error": None,
            "snapshot": None,
            "started_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }
        self._jobs[job_id] = job
        # ring-buffer: never drop still-running/queued jobs
        if len(self._jobs) > 40:
            for old_id in list(self._jobs.keys())[: len(self._jobs) - 40]:
                st = self._jobs.get(old_id, {}).get("status")
                if st not in ("running", "queued"):
                    self._jobs.pop(old_id, None)
        self.last_error = None

        def _finalize_job(stage_val: str | None = None) -> None:
            """Terminal status — cancel always wins (including vs exception)."""
            if job.get("cancel"):
                job["status"] = "cancelled"
                job["error"] = job.get("error") or "cancelled by user"
                job["stage"] = "cancelled"
                return
            sv = stage_val or "error"
            if sv == "error":
                self.last_error = self.pipeline.state.error
                job["status"] = "error"
                job["error"] = self.pipeline.state.error or job.get("error") or "error"
                job["stage"] = sv
            elif sv == "clarify":
                job["status"] = "clarify"
                job["stage"] = sv
            else:
                job["status"] = "done"
                job["stage"] = sv
                if name in ("execute", "pipeline", "worker_rerun"):
                    self._capture_workspace_outputs()
                    if name in ("execute", "pipeline"):
                        self._remember_execute_export()
                    if name == "execute":
                        self.maybe_auto_pack()

        def _run() -> None:
            with lock:
                handlers_on = False

                def _on_stage(data: Any) -> None:
                    if job.get("cancel"):
                        return
                    if getattr(self, "_active_job_id", None) != job_id:
                        return
                    if isinstance(data, dict) and data.get("stage"):
                        job["stage"] = str(data["stage"])
                        try:
                            job["snapshot"] = self.snapshot()
                        except Exception as exc:  # noqa: BLE001
                            job["snapshot_error"] = str(exc)

                def _on_brainstorm(_d: Any) -> None:
                    _on_stage({"stage": "brainstorm"})

                def _on_distill(_d: Any) -> None:
                    _on_stage({"stage": "distill"})

                def _on_flex(_d: Any) -> None:
                    _on_stage({"stage": "flex"})

                def _on_worker(data: Any) -> None:
                    # Prefer concrete worker id so UI pulses only that card
                    wid = ""
                    if isinstance(data, dict):
                        wid = str(data.get("worker") or "").strip()
                    _on_stage({"stage": wid if wid else "work"})

                def _cleanup_handlers() -> None:
                    self.bus.off("pipeline.stage", _on_stage)
                    self.bus.off("pipeline.brainstorm", _on_brainstorm)
                    self.bus.off("pipeline.distill", _on_distill)
                    self.bus.off("pipeline.flex", _on_flex)
                    self.bus.off("pipeline.worker", _on_worker)

                try:
                    if job.get("cancel"):
                        _finalize_job("cancelled")
                        job["snapshot"] = self.snapshot()
                        return
                    self._active_job_id = job_id
                    job["stage"] = "running"
                    # Handlers only while this job owns the pipeline lock
                    self.bus.on("pipeline.stage", _on_stage)
                    self.bus.on("pipeline.brainstorm", _on_brainstorm)
                    self.bus.on("pipeline.distill", _on_distill)
                    self.bus.on("pipeline.flex", _on_flex)
                    self.bus.on("pipeline.worker", _on_worker)
                    handlers_on = True
                    # Cooperative soft-cancel between stages/workers
                    self.pipeline.cancel_check = lambda: bool(job.get("cancel"))
                    try:
                        runner()
                    finally:
                        self.pipeline.cancel_check = None
                    _finalize_job(self.pipeline.state.stage.value)
                    if not job.get("stage"):
                        job["stage"] = self.pipeline.state.stage.value
                    job["snapshot"] = self.snapshot()
                except Exception as exc:  # noqa: BLE001
                    # PipelineCancelled is a subclass of Exception — treat as cancel
                    from gnom_hub.pipeline.orchestrator import PipelineCancelled

                    if job.get("cancel") or isinstance(exc, PipelineCancelled):
                        job["cancel"] = True
                        _finalize_job("cancelled")
                    else:
                        job["status"] = "error"
                        job["error"] = str(exc)
                        job["stage"] = "error"
                        self.last_error = str(exc)
                    try:
                        job["snapshot"] = self.snapshot()
                    except Exception:  # noqa: BLE001
                        pass
                finally:
                    try:
                        self.pipeline.cancel_check = None
                    except Exception:  # noqa: BLE001
                        pass
                    if handlers_on:
                        _cleanup_handlers()
                    if getattr(self, "_active_job_id", None) == job_id:
                        self._active_job_id = None

        t = threading.Thread(target=_run, name=f"{name}-{job_id}", daemon=True)
        t.start()
        return {
            "job_id": job_id,
            "status": "running",
            "stage": "queued",
            "message": f"{name} started — poll /api/jobs/{{id}}",
        }

    def chat_async(self, text: str, *, full: bool = False) -> dict[str, Any]:
        """Async: brainstorm turn by default; full=True runs entire pipeline."""
        self.memory.set_query_hint(text)

        def _runner() -> None:
            if full:
                self.pipeline.plan_mode = getattr(self, "plan_mode", "default") or "default"
                self.pipeline.start(text)
            else:
                self.pipeline.brainstorm_turn(text)

        return self._start_job("brainstorm" if not full else "pipeline", _runner)

    def execute_async(self) -> dict[str, Any]:
        """Async execute after brainstorm."""

        def _runner() -> None:
            self.pipeline.plan_mode = getattr(self, "plan_mode", "default") or "default"
            self.pipeline.execute()

        return self._start_job("execute", _runner)

    def rerun_worker_async(self, worker_id: str) -> dict[str, Any]:
        wid = worker_id

        def _runner() -> None:
            self.pipeline.rerun_worker(wid)

        return self._start_job("worker_rerun", _runner)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        jobs = getattr(self, "_jobs", {})
        job = jobs.get(job_id)
        if not job:
            return None
        out = {
            "id": job["id"],
            "name": job.get("name"),
            "status": job["status"],
            "stage": job.get("stage"),
            "error": job.get("error"),
            "started_at": job.get("started_at") or "",
        }
        if job.get("snapshot"):
            out["snapshot"] = job["snapshot"]
        elif job.get("status") in ("running", "queued") and job.get("stage") in (
            "queued",
            "idle",
            "running",
        ):
            # Do not leak another job's live pipeline into a queued job poll
            out["snapshot"] = None
        else:
            out["snapshot"] = self.snapshot()
        return out

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        """Soft-cancel: mark job cancelled (running thread may still finish)."""
        jobs = getattr(self, "_jobs", {})
        job = jobs.get(job_id)
        if not job:
            raise FileNotFoundError("unknown job")
        if job.get("status") in ("running", "queued") or job.get("stage") == "queued":
            job["cancel"] = True
            job["status"] = "cancelled"
            job["error"] = "cancelled by user"
            job["stage"] = "cancelled"
            self._append_trace("job.cancel", {"id": job_id})
        return {
            "id": job["id"],
            "name": job.get("name"),
            "status": job["status"],
            "stage": job.get("stage"),
            "error": job.get("error"),
        }

    def list_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        """Recent jobs (newest first), without heavy snapshots."""
        jobs = getattr(self, "_jobs", {})
        rows: list[dict[str, Any]] = []
        for j in jobs.values():
            if not isinstance(j, dict):
                continue
            rows.append(
                {
                    "id": j.get("id"),
                    "name": j.get("name") or "job",
                    "status": j.get("status"),
                    "stage": j.get("stage"),
                    "error": j.get("error"),
                    "started_at": j.get("started_at") or "",
                }
            )
        rows.sort(key=lambda r: str(r.get("started_at") or r.get("id") or ""), reverse=True)
        return rows[: max(1, min(50, int(limit)))]

    def clarify_async(self, option: str) -> dict[str, Any]:
        """Async clarify under the same pipeline lock as chat/execute."""
        opt = option

        def _runner() -> None:
            self.pipeline.answer_clarify(opt)

        return self._start_job("clarify", _runner)
