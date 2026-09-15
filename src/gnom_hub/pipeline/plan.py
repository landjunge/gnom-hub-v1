"""Coordinator intake."""

from __future__ import annotations

from gnom_hub.pipeline.models import PipelineStage, PipelineState


class PlanMixin:
    def coordinator_intake(self, user_text: str) -> PipelineState:
        text = (user_text or "").strip()
        if not text:
            self._fail("Empty user text")
            return self._state
        self._state.send_target = "coordinator"
        self._state.user_text = text
        self._state.mode = "brainstorm"
        self._state.error = None
        user = self._record_user(text, "coordinator")
        mem = self.memory.recall(text)
        self._state.memory_context = mem
        reqs, question = self.coordinator.distill(text, text, mem)
        self._state.distilled_requirements = reqs
        self.bus.emit("pipeline.distill", {"requirements": list(reqs)})
        if question is not None:
            self._post_coordinator_clarify(question)
            body = "Coordinator: Rückfrage in Box 1.\n" + str(question.text)
            self._record_reply(
                agent="coordinator",
                text=body,
                in_reply_to=user["message_id"],
                source=self._reply_source(body),
            )
            return self._state
        req_txt = "\n".join(f"- {r}" for r in (reqs or [])[:8]) or "(keine Pakete)"
        body = f"Auftrag geprüft.\n{req_txt}\nArbeit starten liefert in Box 3."
        self._record_reply(
            agent="coordinator",
            text=body,
            in_reply_to=user["message_id"],
            source=self._reply_source(body + " " + req_txt),
        )
        self._set_stage(PipelineStage.brainstorm)
        return self._state
