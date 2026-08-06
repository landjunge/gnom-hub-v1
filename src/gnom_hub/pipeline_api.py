"""Sync chat/execute/clarify/reexecute entrypoints (extracted from Hub)."""

from __future__ import annotations

from typing import Any

from gnom_hub.pipeline.models import PipelineStage, PipelineState


class PipelineApiMixin:
    """Mixin extracted from Hub — pure move."""

    def chat(self, text: str, *, full: bool = False) -> dict[str, Any]:
        """Synchronous chat. Default: brainstorm turn. full=True: whole pipeline."""
        return self.chat_sync(text, full=full)

    def _pipeline_lock_obj(self) -> Any:
        import threading

        if not hasattr(self, "_pipeline_lock"):
            self._pipeline_lock = threading.Lock()
        return self._pipeline_lock

    def chat_sync(self, text: str, *, full: bool = False) -> dict[str, Any]:
        self.last_error = None
        self.memory.set_query_hint(text)
        with self._pipeline_lock_obj():
            if full:
                self.pipeline.plan_mode = getattr(self, "plan_mode", "default") or "default"
                self.pipeline.start(text)
            else:
                self.pipeline.brainstorm_turn(text)
            if self.pipeline.state.error:
                self.last_error = self.pipeline.state.error
            elif full and self.pipeline.state.stage.value == "done":
                self._capture_workspace_outputs()
                self._remember_execute_export()
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
