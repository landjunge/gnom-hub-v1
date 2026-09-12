"""Sync chat/execute/clarify/reexecute entrypoints (extracted from Hub)."""

from __future__ import annotations

from typing import Any

from gnom_hub.pipeline.models import PipelineStage, PipelineState


class PipelineApiMixin:
    """Mixin extracted from Hub — pure move."""

    def chat(self, text: str, *, full: bool = False, target: str = "brainstorm") -> dict[str, Any]:
        """Synchronous chat. Default: brainstorm turn. full=True: whole pipeline."""
        return self.chat_sync(text, full=full, target=target)

    def _pipeline_lock_obj(self) -> Any:
        import threading

        if not hasattr(self, "_pipeline_lock"):
            self._pipeline_lock = threading.Lock()
        return self._pipeline_lock

    def chat_sync(
        self, text: str, *, full: bool = False, target: str = "brainstorm"
    ) -> dict[str, Any]:
        self.last_error = None
        self.memory.set_query_hint(text)
        with self._pipeline_lock_obj():
            if full:
                self.pipeline.plan_mode = getattr(self, "plan_mode", "default") or "default"
                self.pipeline.start(text)
            else:
                # Send = target route + Flex Box 1. Execute only via execute() / start_work yes.
                self.pipeline.plan_mode = getattr(self, "plan_mode", "default") or "default"
                self.pipeline.chat_turn(text, target=target)
            if self.pipeline.state.error:
                self.last_error = self.pipeline.state.error
            elif self.pipeline.state.stage.value == "done":
                self._capture_workspace_outputs()
                self._remember_execute_export()
                if full:
                    self.maybe_auto_pack()
            return self.snapshot()

    def execute_sync(self) -> dict[str, Any]:
        """Run distill → flex → workers from accumulated brainstorm."""
        self.last_error = None
        with self._pipeline_lock_obj():
            # Single source: hub.plan_mode → pipeline before coordinate
            self.pipeline.plan_mode = getattr(self, "plan_mode", "default") or "default"
            self.pipeline.execute()
            if self.pipeline.state.error:
                self.last_error = self.pipeline.state.error
            elif self.pipeline.state.stage.value == "done":
                self._capture_workspace_outputs()
                self._remember_execute_export()
                self.maybe_auto_pack()
            if self.pipeline.state.stage.value in ("done", "error"):
                try:
                    self.set_god_mode(False, reason="user:job_end")
                except Exception:  # noqa: BLE001
                    pass
            return self.snapshot()

    def rerun_worker_sync(self, worker_id: str) -> dict[str, Any]:
        """Re-run one worker from last task."""
        self.last_error = None
        with self._pipeline_lock_obj():
            self.pipeline.rerun_worker(worker_id)
            if self.pipeline.state.error:
                self.last_error = self.pipeline.state.error
            elif self.pipeline.state.stage.value == "done":
                self._capture_workspace_outputs()
            return self.snapshot()

    def clarify(self, option: str) -> dict[str, Any]:
        """Synchronous clarify (also used after async reaches clarify)."""
        self.last_error = None
        with self._pipeline_lock_obj():
            self.pipeline.answer_clarify(option)
            if self.pipeline.state.error:
                self.last_error = self.pipeline.state.error
            return self.snapshot()

    def flex_ask(
        self,
        *,
        agent_id: str,
        text: str,
        job_id: str = "",
        task_id: str = "",
        component: str = "yes_no",
        options: list[str] | None = None,
    ) -> dict[str, Any]:
        """Coordinator/Worker structured ask → Flex Box 1. Never Execute."""
        desk = getattr(self.pipeline, "flex_desk", None)
        if desk is None:
            raise TypeError("flex desk missing")
        if not desk.job_id:
            desk.bind_job(job_id or getattr(self.pipeline.state, "flex_job_id", "") or "desk")
        out = desk.ask(
            agent_id=agent_id,
            text=text,
            job_id=job_id or desk.job_id,
            task_id=task_id,
            component=component,
            options=options,
        )
        sync = getattr(self.pipeline, "_sync_flex_state", None)
        if callable(sync):
            sync()
        snap = self.snapshot()
        snap["flex_ask"] = out
        return snap

    def flex_answer(
        self,
        question_id: str,
        value: object,
        *,
        job_id: str = "",
        sync: bool = True,
    ) -> dict[str, Any]:
        """User answer in Box 1. Start-work yes → central execute(), not Flex."""
        desk = getattr(self.pipeline, "flex_desk", None)
        if desk is None:
            raise TypeError("flex desk missing")
        out = desk.answer(question_id, value, job_id=job_id)
        sync_st = getattr(self.pipeline, "_sync_flex_state", None)
        if callable(sync_st):
            sync_st()
        if not out.get("ok"):
            snap = self.snapshot()
            snap["flex_answer"] = out
            return snap
        if out.get("wants_start_work"):
            if sync:
                snap = self.execute_sync()
            else:
                snap = self.execute_async()
            if isinstance(snap, dict):
                snap["flex_answer"] = out
            return snap
        agent = str(out.get("agent_id") or "")
        apply_fn = getattr(self.pipeline, "apply_flex_answer", None)
        if callable(apply_fn) and agent:
            apply_fn(out)
        if agent == "coordinator":
            val = str(out.get("value") or "")
            if self.pipeline.state.pending_question is None:
                from gnom_hub.pipeline.models import DistillQuestion, PipelineStage

                self.pipeline.state.pending_question = DistillQuestion(
                    id=str(out.get("question_id") or "q1"),
                    text="Wie soll ich vorgehen?",
                    options=["Schnell und einfach", "Gründlich und robust", val],
                )
                self.pipeline.state.stage = PipelineStage.clarify
            if sync:
                return self.clarify(val)
            snap = self.clarify(val)
            if isinstance(snap, dict):
                snap["flex_answer"] = out
            return snap
        wait = getattr(self.pipeline.state, "flex_wait_agent", "") or ""
        yes = str(out.get("value") or "").lower().strip(" !.。") in {
            "ja",
            "yes",
            "y",
            "ok",
        }
        if wait and wait == agent:
            self.pipeline.state.flex_wait_agent = ""
            cont = getattr(self.pipeline, "continue_after_flex_ask", None)
            if callable(cont):
                cont()
        elif (
            yes and str(out.get("task_id") or "") == "nachbesserung" and agent.startswith("worker")
        ):
            self.pipeline.rerun_worker(agent)
        snap = self.snapshot()
        snap["flex_answer"] = out
        return snap

    def resume_deferred_clarify(self, index: int = -1) -> dict[str, Any]:
        """Re-open a Later-parked clarify (sync, no workers until answered)."""
        self.last_error = None
        with self._pipeline_lock_obj():
            fn = getattr(self.pipeline, "resume_deferred_clarify", None)
            if not callable(fn):
                raise TypeError("resume deferred not supported")
            fn(index)
            return self.snapshot()

    def restore_for_reexecute(
        self,
        *,
        user_text: str,
        brainstorm_notes: str,
        brainstorm_turns: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Restore brainstorm context so a subsequent Execute re-runs workers."""
        text = (user_text or "").strip()
        notes = (brainstorm_notes or "").strip()
        if not text and not notes:
            raise ValueError("nothing to re-execute")
        turns = list(brainstorm_turns or [])
        if not notes and turns:
            # format like orchestrator
            lines: list[str] = []
            for t in turns:
                role = str(t.get("role") or "")
                ttxt = str(t.get("text") or "").strip()
                if not ttxt:
                    continue
                if role == "user":
                    lines.append(f"You: {ttxt}")
                else:
                    lines.append(f"Brainstorm:\n{ttxt}")
                lines.append("")
            notes = "\n".join(lines).strip()
        if not text and turns:
            for t in turns:
                if t.get("role") == "user" and str(t.get("text") or "").strip():
                    text = str(t["text"]).strip()
                    break
        # H6: serialize against in-flight pipeline jobs
        with self._pipeline_lock_obj():
            self.pipeline._state = PipelineState(
                stage=PipelineStage.brainstorm,
                mode="brainstorm",
                user_text=text,
                brainstorm_notes=notes,
                brainstorm_turns=turns,
            )
            self.last_error = None
            self._append_trace("session.reexecute.restore", {"user": text[:80]})
            return self.snapshot()
