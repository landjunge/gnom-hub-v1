"""start/execute and worker fan-out."""

from __future__ import annotations

from gnom_hub.flex_desk import parse_flex_ask
from gnom_hub.pipeline.constants import PipelineCancelled
from gnom_hub.pipeline.helpers import (
    _definition_of_done,
    _format_turns,
    _pick_execute_task,
    _prefetch_worker_tools,
    _quality_check,
    _validate_worker_draft,
)
from gnom_hub.pipeline.models import PipelineStage, PipelineState


class DispatchMixin:
    def _worker_ids_for_plan(self) -> list[str]:
        """Flag (send_target) is the assigned worker. HTML/default no longer always Worker 1."""
        ids = [wid for wid, w in self._workers.items() if w.enabled]
        pref = str(getattr(self._state, "send_target", "") or "").strip().lower()
        if pref in ids:
            return [pref] + [w for w in ids if w != pref]
        return ids

    def _offer_start_work(self, *, reason: str, workers: str = "") -> None:
        """Legacy no-op. Start is the Arbeit-starten button, never Box 1."""
        del reason, workers

    def _offer_judgment(self) -> None:
        """Box 1 after a real deliverable. Key missing beats Passt das."""
        from gnom_hub.snapshot_ops import _deliverable_ok

        if not _deliverable_ok(self._state):
            return
        self._ensure_flex_job()
        if self._results_missing_key():
            self.flex_desk.ask(
                agent_id="flex",
                job_id=self.flex_desk.job_id,
                task_id="key_missing",
                component="yes_no",
                text=(
                    "Key fehlt. In System einen echten Schlüssel eintragen, dann Arbeit starten."
                ),
                options=["Verstanden"],
                entry_type="blockiert",
            )
        else:
            self.flex_desk.offer_judgment()
        self._sync_flex_state()
        vis = self.flex_desk.visible_question()
        self.bus.emit(
            "pipeline.flex_ask",
            {
                "reason": "judgment",
                "question_id": vis.question_id if vis is not None else None,
                "component": vis.component if vis is not None else "judgment",
            },
        )

    def _results_missing_key(self) -> bool:
        marks = (
            "kein deliverable",
            "llm/key",
            "deepseek_api_key",
            "kein nutzbarer llm",
        )
        blobs: list[str] = []
        for r in list(self._state.worker_results or []):
            blobs.append(str(r or "").lower())
        if not blobs:
            return False
        hits = sum(1 for b in blobs if any(m in b for m in marks))
        return hits >= max(1, (len(blobs) + 1) // 2)

    def start(self, user_text: str) -> PipelineState:
        text = user_text.strip()
        self._state = PipelineState(user_text=text, mode="full")
        self._clarified_once = False
        try:
            if not text:
                self._fail("Empty user text")
                return self._state

            self._stage_t0 = None
            self._stage_name = None
            self._check_cancel()
            if self._try_browser_nav_short_circuit(text):
                return self._state

            self._begin_stage_timing("memory")
            self.bus.emit("pipeline.stage", {"stage": "memory"})
            mem = self.memory.recall(text)
            self._state.memory_context = mem
            if mem:
                self.bus.emit("pipeline.memory_context", {"context": mem})
            self._close_stage_timing()

            self._check_cancel()
            if self.brainstorm.enabled:
                self._set_stage(PipelineStage.brainstorm)
                notes = self.brainstorm.run(text, mem, history=[])
                self._state.brainstorm_notes = notes
                self._state.brainstorm_turns = [
                    {"role": "user", "text": text},
                    {"role": "brainstorm", "text": notes},
                ]
                self.bus.emit("pipeline.brainstorm", {"notes": notes, "mode": "full"})

            self._check_cancel()
            self._set_stage(PipelineStage.distill)
            reqs, question = self.coordinator.distill(text, self._state.brainstorm_notes, mem)
            self._state.distilled_requirements = reqs
            self.bus.emit("pipeline.distill", {"requirements": list(reqs)})

            self._check_cancel()
            if question is not None and not self._clarified_once:
                self._post_coordinator_clarify(question)
                return self._state

            self._check_cancel()
            self._run_flex_coord_workers()
        except PipelineCancelled:
            return self._state
        except Exception as exc:  # noqa: BLE001
            self._fail(str(exc))
        return self._state
