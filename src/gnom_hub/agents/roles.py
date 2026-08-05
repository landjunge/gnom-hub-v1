"""V1 role agents — Brainstorm & Flex; others in roles_ext."""

from __future__ import annotations

from gnom_hub.agents.base import BaseAgent
from gnom_hub.agents.roles_ext import (  # noqa: F401
    CoordinatorAgent,
    MemoryAgent,
    WorkerAgent,
)
from gnom_hub.agents.roles_helpers import (  # noqa: F401
    _brainstorm_user_payload,
    _format_brainstorm_history,
    _is_garbage_fact,
    _lines,
    _needs_clarify,
    _sanitize_memory_ctx,
    _stub_brainstorm,
    _with_memory,
)


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
                        "- Do NOT invent an unrelated product (todo app, kanban, etc.).\n"
                        "- If the user asks about THIS hub (Gnom-Hub bugs/UX), answer on that topic.\n"
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


class FlexAgent(BaseAgent):
    def run(self, user_text: str, requirements: list[str], memory_ctx: str = "") -> str:
        if not self.enabled:
            return ""
        preset = (self.state.preset or "security").lower()
        self.emit_active(True)
        try:
            prompts = {
                "security": (
                    "You are Flex/Security. List 3–5 concrete security risks "
                    "(auth, secrets, paths, abuse). One line each. Match user language."
                ),
                "researcher": (
                    "You are Flex/Researcher. List 3–5 open questions or missing facts. "
                    "One line each. Match user language."
                ),
                "neutral": (
                    "You are Flex/Neutral. List 3–5 trade-offs. One line each. Match user language."
                ),
            }
            system = prompts.get(preset, prompts["security"])
            body = f"Auftrag: {user_text}\nAnforderungen:\n" + "\n".join(
                f"- {r}" for r in requirements[:6]
            )
            if self.has_llm():
                try:
                    return self.ask(
                        system=system,
                        user=_with_memory(body, memory_ctx),
                        max_tokens=350,
                        temperature=0.4,
                    )
                except Exception as exc:  # noqa: BLE001
                    self.bus.emit(
                        "pipeline.warning",
                        {"stage": "flex", "error": str(exc)},
                    )
            if preset == "researcher":
                return "• Welche Zielgruppe?\n• Welche Datenquellen?\n• Erfolgsmetrik in 1 Satz?"
            if preset == "neutral":
                return (
                    "• Geschwindigkeit vs. Qualität\n"
                    "• Manuell vs. Automatisierung\n"
                    "• Lokal vs. Cloud"
                )
            return (
                "• Keine Secrets im Frontend\n"
                "• Eingaben validieren\n"
                "• Schreibzugriffe auf data/ begrenzen"
            )
        finally:
            self.emit_active(False)
