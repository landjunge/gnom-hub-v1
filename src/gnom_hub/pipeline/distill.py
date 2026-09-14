"""Clarify / distill pause and resume."""

from __future__ import annotations

from typing import Any

from gnom_hub.pipeline.constants import PipelineCancelled
from gnom_hub.pipeline.models import PipelineStage, PipelineState


class DistillMixin:
    def _post_coordinator_clarify(self, question: Any) -> None:
        self._state.pending_question = question
        self._ensure_flex_job()
        self.flex_desk.ask(
            agent_id="coordinator",
            job_id=self.flex_desk.job_id,
            task_id="clarify",
            text=question.text,
            component="single_select",
            options=list(question.options),
        )
        self._sync_flex_state()
        self._set_stage(PipelineStage.clarify)
        self.bus.emit(
            "pipeline.question",
            {
                "id": question.id,
                "text": question.text,
                "options": list(question.options),
            },
        )

    @staticmethod
    def _is_defer_clarify_option(option: str) -> bool:
        low = (option or "").strip().lower()
        if not low:
            return False
        defer_exact = {
            "later",
            "später",
            "spaeter",
            "spater",
            "not now",
            "später entscheiden",
            "spaeter entscheiden",
            "spater entscheiden",
            "decide later",
            "remind me later",
        }
        if low in defer_exact:
            return True
        return low.startswith(("später", "spaeter", "later"))

    def _defer_clarify(self, answer: str, q: Any) -> PipelineState:
        """Park clarify without running workers — leave desk usable (brainstorm)."""
        qid = str(getattr(q, "id", "") or "q")
        qtext = str(getattr(q, "text", "") or "").strip()
        entry = {
            "id": qid,
            "text": qtext[:300],
            "option": answer,
        }
        deferred = list(self._state.deferred_clarifies or [])
        deferred.append(entry)
        self._state.deferred_clarifies = deferred[-12:]
        note = f"Deferred clarify ({answer}): {qtext[:180]}"
        if note and note not in (self._state.distilled_requirements or []):
            self._state.distilled_requirements.append(note)
        try:
            store = getattr(self, "memory_store", None)
            hot = getattr(store, "hot", None) if store is not None else None
            if hot is not None and hasattr(hot, "add_fact"):
                hot.add_fact(note[:160])
                if hasattr(hot, "save"):
                    hot.save()
        except Exception:  # noqa: BLE001
            pass
        self._state.pending_question = None
        self._state.error = None
        self._state.mode = "brainstorm"
        self._set_stage(PipelineStage.brainstorm)
        self._clarified_once = True
        self.bus.emit(
            "pipeline.clarify_deferred",
            {
                "id": qid,
                "text": qtext[:200],
                "option": answer,
                "count": len(self._state.deferred_clarifies),
            },
        )
        self.bus.emit(
            "pipeline.stage",
            {"stage": "brainstorm", "deferred_clarify": True},
        )
        return self._state

    def resume_deferred_clarify(self, index: int = -1) -> PipelineState:
        """Re-open a parked Later clarify as active pending_question (no auto-workers)."""
        from gnom_hub.pipeline.models import DistillQuestion

        deferred = list(self._state.deferred_clarifies or [])
        if not deferred:
            raise ValueError("No deferred clarifications")
        idx = int(index)
        if idx < 0:
            idx = len(deferred) + idx
        if idx < 0 or idx >= len(deferred):
            raise ValueError("deferred index out of range")
        entry = deferred.pop(idx)
        self._state.deferred_clarifies = deferred
        qid = str(entry.get("id") or f"deferred-{idx}")
        qtext = str(entry.get("text") or "Please clarify").strip() or "Please clarify"
        self._state.pending_question = DistillQuestion(
            id=qid,
            text=qtext,
            options=["Yes", "No", "Whatever", "Later"],
        )
        self._state.error = None
        self._state.mode = "execute"
        self._clarified_once = False
        self._set_stage(PipelineStage.clarify)
        self.bus.emit(
            "pipeline.clarify_resumed",
            {"id": qid, "text": qtext[:200], "remaining": len(deferred)},
        )
        self.bus.emit("pipeline.stage", {"stage": "clarify", "resumed": True})
        return self._state

    def answer_clarify(self, option: str) -> PipelineState:
        """
        Apply clarify answer then run workers.

        H2: keep ``pending_question`` until work reaches a terminal success
        (done). On cancel/error the question stays so the user can re-answer.

        Special: **Later** / Später → defer (no workers, no zombie clarify stage).
        """
        if self._state.stage != PipelineStage.clarify or self._state.pending_question is None:
            raise ValueError("No pending clarification question")
        answer = option.strip()
        q = self._state.pending_question
        if self._is_defer_clarify_option(answer):
            return self._defer_clarify(answer, q)
        for fq in list(self.flex_desk.open_questions()):
            if fq.agent_id == "coordinator" and fq.status == "open":
                self.flex_desk.answer(fq.question_id, answer, job_id=fq.job_id)
        self._sync_flex_state()
        clarify_line = f"User clarified ({q.id}): {answer}"
        if clarify_line not in self._state.distilled_requirements:
            self._state.distilled_requirements.append(clarify_line)
        # Prevent re-asking on a later distill, but do not drop the question yet
        self._clarified_once = True
        try:
            self._run_flex_coord_workers()
        except PipelineCancelled:
            # Soft-cancel may restore brainstorm — put user back on clarify if needed
            self._state.pending_question = q
            if self._state.stage != PipelineStage.done:
                self._state.stage = PipelineStage.clarify
            return self._state
        except Exception as exc:  # noqa: BLE001
            self._fail(str(exc))
            self._state.pending_question = q
            self._state.stage = PipelineStage.clarify
            return self._state

        if self._state.stage == PipelineStage.done:
            self._state.pending_question = None
        elif self._state.stage == PipelineStage.error:
            self._state.pending_question = q
            self._state.stage = PipelineStage.clarify
        else:
            # Cancel restored brainstorm / mid-stage abort — keep question
            self._state.pending_question = q
        return self._state
