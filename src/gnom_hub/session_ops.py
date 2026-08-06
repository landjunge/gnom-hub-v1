"""Checkpoint, save, reset, clean (extracted from Hub — pure move)."""

from __future__ import annotations

import json
from typing import Any

from gnom_hub.agents.manager import AgentManager
from gnom_hub.memory.atomic import atomic_write_text
from gnom_hub.pipeline.models import PipelineStage


class SessionOpsMixin:
    """Mixin extracted from Hub — pure move."""

    def save_checkpoint(self) -> dict[str, Any]:
        """Persist pipeline state for resume (plan §8.1 light checkpoint)."""
        st = self.pipeline.state
        payload = {
            "version": 1,
            "stage": st.stage.value,
            "mode": st.mode,
            "user_text": st.user_text,
            "memory_context": st.memory_context,
            "brainstorm_notes": st.brainstorm_notes,
            "brainstorm_turns": list(st.brainstorm_turns or []),
            "distilled_requirements": list(st.distilled_requirements),
            "flex_notes": st.flex_notes,
            "worker_results": list(st.worker_results),
            "worker_outputs": list(st.worker_outputs or []),
            "quality_notes": st.quality_notes,
            "warnings": list(st.warnings),
            "error": st.error,
            "pending_question": (
                {
                    "id": st.pending_question.id,
                    "text": st.pending_question.text,
                    "options": list(st.pending_question.options),
                }
                if st.pending_question
                else None
            ),
        }
        self._checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self._checkpoint_path,
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        )
        self._append_trace("checkpoint.save", {"path": str(self._checkpoint_path)})
        return {"ok": True, "path": str(self._checkpoint_path)}

    def load_checkpoint(self) -> dict[str, Any]:
        """Restore pipeline state from checkpoint file."""
        from gnom_hub.pipeline.models import DistillQuestion, PipelineState

        path = self._checkpoint_path
        if not path.is_file():
            raise FileNotFoundError("no checkpoint")
        data = json.loads(path.read_text(encoding="utf-8"))
        q = None
        pq = data.get("pending_question")
        if isinstance(pq, dict) and pq.get("text"):
            q = DistillQuestion(
                id=str(pq.get("id") or "q1"),
                text=str(pq["text"]),
                options=list(pq.get("options") or ["Yes", "No", "Whatever", "Later"]),
            )
        stage_raw = str(data.get("stage") or "idle")
        try:
            stage = PipelineStage(stage_raw)
        except ValueError:
            stage = PipelineStage.idle
        self.pipeline._state = PipelineState(
            stage=stage,
            user_text=str(data.get("user_text") or ""),
            memory_context=str(data.get("memory_context") or ""),
            brainstorm_notes=str(data.get("brainstorm_notes") or ""),
            brainstorm_turns=list(data.get("brainstorm_turns") or []),
            mode=str(data.get("mode") or "brainstorm"),
            distilled_requirements=list(data.get("distilled_requirements") or []),
            flex_notes=str(data.get("flex_notes") or ""),
            pending_question=q,
            worker_results=list(data.get("worker_results") or []),
            worker_outputs=list(data.get("worker_outputs") or []),
            quality_notes=str(data.get("quality_notes") or ""),
            warnings=list(data.get("warnings") or []),
            error=data.get("error"),
        )
        self._append_trace("checkpoint.load", {"stage": stage.value})
        return self.snapshot()

    def save(self) -> dict[str, Any]:
        self.hot.save()
        self.warm.save()
        agents_path = self._save_agent_state()
        return {
            "ok": True,
            "path": str(self.hot.session_path),
            "warm_path": str(self.warm.facts_path),
            "agents_path": str(agents_path),
            "summary": self.hot.get_context_summary(),
            "warm_facts": len(self.warm.all_facts()),
            "canvas_nodes": len(self.hot.canvas.nodes),
        }

    def reset_session(
        self,
        *,
        keep_agents: bool = True,
        clear_warm: bool = False,
        archive: bool = True,
    ) -> dict[str, Any]:
        """Clear HOT session + pipeline. Optionally archive to COLD first. WARM kept unless clear_warm."""
        # Soft-cancel any in-flight jobs so they cannot overwrite a fresh pipeline
        cancelled_jobs = 0
        jobs = getattr(self, "_jobs", None)
        if not isinstance(jobs, dict):
            jobs = {}
            self._jobs = jobs
        for jid, job in list(jobs.items()):
            if isinstance(job, dict) and job.get("status") in ("running", "queued"):
                job["cancel"] = True
                job["status"] = "cancelled"
                job["error"] = job.get("error") or "cancelled by reset"
                job["stage"] = "cancelled"
                cancelled_jobs += 1
                _ = jid
        self._active_job_id = None

        archived = None
        with self._pipeline_lock_obj():
            if archive and (self.hot.session.get("messages") or self.hot.session.get("facts")):
                archived = self.archive_cold(label="auto-reset")
            self.hot.clear(save=True)
            if clear_warm:
                self.warm.clear()
            if not keep_agents:
                self.agents = AgentManager(self.bus)
                self.agents.on_start()
            self.pipeline = self._new_pipeline()
            self.last_error = None
            self._agent_thoughts = {}
            # Drop light checkpoint so restore cannot re-inject old brainstorm
            if self._checkpoint_path.is_file():
                try:
                    self._checkpoint_path.unlink()
                except OSError:
                    pass
            snap = self.snapshot()
        if archived:
            snap["archived"] = archived
        if cancelled_jobs:
            snap["cancelled_jobs"] = cancelled_jobs
        return snap

    def clean_state(self) -> dict[str, Any]:
        """
        One-click clean state (plan §7): clear HOT + temp workspace + pipeline,
        keep WARM long-term memory and agent toggles.
        """
        jobs = getattr(self, "_jobs", None)
        if not isinstance(jobs, dict):
            jobs = {}
            self._jobs = jobs
        for job in list(jobs.values()):
            if isinstance(job, dict) and job.get("status") in ("running", "queued"):
                job["cancel"] = True
                job["status"] = "cancelled"
                job["error"] = job.get("error") or "cancelled by clean"
                job["stage"] = "cancelled"
        self._active_job_id = None
        archived = None
        with self._pipeline_lock_obj():
            if self.hot.session.get("messages") or self.hot.session.get("facts"):
                archived = self.archive_cold(label="clean-state")
            self.hot.clear(save=True)
            removed = self.workspace.clear_temp()
            self.pipeline = self._new_pipeline()
            self.last_error = None
            self.trace = []
            self._agent_thoughts = {}
            if self._checkpoint_path.is_file():
                try:
                    self._checkpoint_path.unlink()
                except OSError:
                    pass
            snap = self.snapshot()
        # Clean is a hard wipe — drop pinned export too
        self._last_execute_export = None
        snap["clean"] = {
            "ok": True,
            "temp_removed": removed,
            "archived": archived,
            "warm_kept": True,
        }
        return snap
