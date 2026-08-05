"""V1 role agents — one class per plan role."""

from __future__ import annotations

import re
from typing import Any

from gnom_hub.agents.base import BaseAgent
from gnom_hub.core.event_bus import EventBus
from gnom_hub.pipeline.models import DistillQuestion


class BrainstormAgent(BaseAgent):
    """Free brainstorm partner — dialogue, not a one-shot idea dump."""

    def run(
        self,
        user_text: str,
        memory_ctx: str = "",
        history: list[dict] | None = None,
    ) -> str:
        if not self.enabled:
            return ""
        self.emit_active(True)
        try:
            hist = history or []
            if self.has_llm():
                try:
                    # True multi-turn: prior user/assistant messages, not a flat dump only
                    prior = [
                        {
                            "role": str(t.get("role") or "user"),
                            "content": str(t.get("text") or t.get("content") or ""),
                        }
                        for t in hist[-16:]
                        if isinstance(t, dict)
                        and str(t.get("text") or t.get("content") or "").strip()
                    ]
                    system = (
                        "You are the Brainstorm partner in Gnom-Hub.\n"
                        "Your job is FREE brainstorming with the user — a real dialogue, "
                        "not a one-shot idea dump and not execution.\n"
                        "Rules:\n"
                        "- Match the user language (DE/EN).\n"
                        "- Use the full prior dialogue; never restart from zero if history exists.\n"
                        "- React to THIS message; build on earlier ideas.\n"
                        "- Offer 3–6 concrete ideas, angles, or questions — not a finished plan.\n"
                        "- Ask at most ONE short follow-up if something is unclear.\n"
                        "- Do NOT start implementing, writing full code, or running the pipeline.\n"
                        "- Do NOT describe or redesign Gnom-Hub itself.\n"
                        "- No corporate fluff. Be direct and useful.\n"
                        "- If the user only refines (e.g. 'more on X'), go deeper on that."
                    )
                    return self.ask(
                        system=system,
                        user=_with_memory(f"USER MESSAGE:\n{user_text}", memory_ctx),
                        prior=prior,
                        max_tokens=700,
                        temperature=0.9,
                    )
                except Exception as exc:  # noqa: BLE001
                    self.bus.emit(
                        "pipeline.warning",
                        {"stage": "brainstorm", "error": str(exc)},
                    )
            return _stub_brainstorm(user_text, hist)
        finally:
            self.emit_active(False)
