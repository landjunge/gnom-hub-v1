"""Finish, memory notes, quality close-out."""

from __future__ import annotations

from gnom_hub.memory.secrets import filter_secrets, looks_like_secret
from gnom_hub.pipeline.models import PipelineStage
from gnom_hub.snapshot_ops import _deliverable_ok
from gnom_hub.threaddesk_ops import write_handoff


class PersistMixin:
    def _offer_memory_keep(self, facts: list[str]) -> None:
        """Box 1: Behalten writes WARM. Verwerfen does not. Never Execute."""
        clean = filter_secrets([f for f in facts if str(f).strip()])[:3]
        if not clean:
            self._state.memory_proposals = []
            return
        self._state.memory_proposals = clean
        self._ensure_flex_job()
        bullets = "\n".join(f"• {f}" for f in clean)
        text = (
            f"Memory schlägt vor, das dauerhaft zu behalten:\n{bullets}\nSoll genau das nach WARM?"
        )
        self.flex_desk.ask(
            agent_id="memory",
            text=text,
            component="memory_keep",
            options=["Behalten", "Verwerfen"],
            assignment_id="MEM1",
            entry_type="freigabe",
            task_id="memory_keep",
        )
        self._sync_flex_state()
        self.bus.emit("pipeline.memory_propose", {"facts": clean})
