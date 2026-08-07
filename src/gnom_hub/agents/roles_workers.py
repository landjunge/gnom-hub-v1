"""Worker and Memory role agents."""

from __future__ import annotations

from typing import Any

from gnom_hub.agents.base import BaseAgent
from gnom_hub.agents.roles_helpers import (
    _is_flex_meta_requirement,
    _is_garbage_fact,
    _with_memory,
)
from gnom_hub.core.event_bus import EventBus


class WorkerAgent(BaseAgent):
    def run(
        self,
        task: str,
        user_text: str,
        requirements: list[str],
        memory_ctx: str = "",
    ) -> str:
        if not self.enabled:
            return ""
        self.emit_active(True)
        try:
            if self.has_llm():
                try:
                    body = f"Aufgabe: {task}\nOriginal: {user_text}\nAnforderungen:\n" + "\n".join(
                        f"- {r}" for r in requirements[:5]
                    )
                    blob = f"{task}\n{user_text}".lower()
                    wants_html = any(
                        k in blob
                        for k in (
                            "html",
                            "landing",
                            "webpage",
                            "web page",
                            "css",
                            "seite",
                            "website",
                            "frontend",
                        )
                    )
                    max_tok = 3200 if wants_html else 1800
                    return self.ask(
                        system=(
                            "You are a Worker agent. Deliver a concrete useful result "
                            "for the assigned task (plan, structure, checklist, draft, "
                            "or full HTML when the task is a page/UI).\n"
                            "PRIORITY ORDER (mandatory — do not reverse):\n"
                            "  1) Complete structure / skeleton (always finish the file)\n"
                            "  2) Core interactive behavior (JS/handlers, DOM updates)\n"
                            "  3) Error/empty states for those core flows\n"
                            "  4) CSS/styling LAST (max ~30% of effort; minimal layout first)\n"
                            "Budget: ~70% functions+structure, ~30% styling. If near limit, "
                            "CUT CSS — never omit </html> or core interactions.\n"
                            "If HTML/landing/page/UI:\n"
                            "  - ONE complete file: <!DOCTYPE html> … </html>\n"
                            "  - At least one real interaction "
                            "(onclick= or addEventListener or form submit handler)\n"
                            "  - Prefer working demo over pretty design\n"
                            "Work on the USER task only. Match user language."
                        ),
                        user=_with_memory(body, memory_ctx),
                        max_tokens=max_tok,
                        temperature=0.45,
                    )
                except Exception as exc:  # noqa: BLE001
                    self.bus.emit(
                        "pipeline.warning",
                        {"stage": self.id, "error": str(exc)},
                    )
            return (
                f"{self.state.name} Ergebnis\n"
                f"Aufgabe: {task.splitlines()[0][:140]}\n"
                "• Schritt 1: Anforderungen klären\n"
                "• Schritt 2: MVP skizzieren\n"
                "• Schritt 3: Nächsten Schritt vorschlagen\n"
                "(Stub — mit DeepSeek-Key echte Ausgabe.)"
            )
        finally:
            self.emit_active(False)


class MemoryAgent(BaseAgent):
    """Always-on Memory agent — holds the red thread."""

    def __init__(
        self,
        state: Any,
        bus: EventBus,
        llm: Any | None = None,
        memory: Any | None = None,
    ) -> None:
        super().__init__(state, bus, llm)
        self.memory = memory
        self.state.enabled = True
        self.state.toggleable = False

    def recall(self, user_text: str = "") -> str:
        self.emit_active(True)
        try:
            raw = ""
            if self.memory is not None:
                set_q = getattr(self.memory, "set_query_hint", None)
                if callable(set_q) and user_text:
                    set_q(user_text)
                fn = getattr(self.memory, "pipeline_context", None)
                if callable(fn):
                    raw = str(fn() or "").strip()
            from gnom_hub.agents.roles_helpers import _sanitize_memory_ctx

            raw = _sanitize_memory_ctx(raw)
            if not raw:
                return ""
            if not self.has_llm() or not user_text.strip():
                return raw[:900]
            try:
                curated = self.ask(
                    system=(
                        "You are the Memory agent. From the stored context, select only "
                        "facts relevant to the CURRENT user task. "
                        "Ignore HTML, code, other projects, and pipeline meta. "
                        "Output 2–6 short bullet facts. No preamble. "
                        "If nothing is relevant: (no relevant memory)"
                    ),
                    user=f"Task:\n{user_text}\n\nStored context:\n{raw[:2200]}",
                    max_tokens=280,
                    temperature=0.1,
                )
                cleaned = _sanitize_memory_ctx(curated or "")
                if not cleaned or cleaned.lower().startswith("(no relevant"):
                    return ""
                return cleaned[:900]
            except Exception as exc:  # noqa: BLE001
                self.bus.emit(
                    "pipeline.warning",
                    {"stage": "memory_recall", "error": str(exc)},
                )
                return raw[:900]
        finally:
            self.emit_active(False)

    def store(
        self,
        *,
        user_text: str,
        requirements: list[str],
        brainstorm: str,
        flex_notes: str,
        results: list[str],
    ) -> None:
        self.emit_active(True)
        try:
            clean_reqs = [
                r
                for r in requirements
                if not _is_flex_meta_requirement(r)
                and 8 <= len(r) < 160
                and not _is_garbage_fact(r)
            ][:5]
            self.bus.emit(
                "pipeline.memory_hint",
                {
                    "user_text": user_text,
                    "requirements": clean_reqs,
                    "results": results[:2],
                    "brainstorm_notes": brainstorm,
                    "flex_notes": flex_notes,
                },
            )
            if self.has_llm():
                try:
                    safe_results: list[str] = []
                    for r in results[:2]:
                        snip = (r or "").strip()
                        if not snip or _is_garbage_fact(snip[:200]):
                            continue
                        if "```" in snip:
                            snip = snip.split("```", 1)[0].strip()
                        if snip and len(snip) >= 20:
                            safe_results.append(snip[:280])
                    pack = (
                        f"User task: {user_text}\n"
                        f"Requirements:\n"
                        + "\n".join(f"- {r}" for r in clean_reqs)
                        + f"\nBrainstorm head:\n{(brainstorm or '')[:400]}\n"
                    )
                    if safe_results:
                        pack += "Worker notes (no code):\n" + "\n---\n".join(safe_results)
                    curated = self.ask(
                        system=(
                            "You are the Memory agent. Extract 0–3 DURABLE facts only.\n"
                            "Durable = user preference, brand/product name, standing constraint, "
                            "or a decision that should survive a NEW unrelated session.\n"
                            "NEVER store: HTML/CSS/JS, code, session requirements lists, "
                            "worker drafts, test chatter, empty meta, or pipeline status.\n"
                            "One short fact per line. No numbering. No intro.\n"
                            "If nothing durable: (none)"
                        ),
                        user=pack,
                        max_tokens=180,
                        temperature=0.1,
                    )
                    facts: list[str] = []
                    for ln in (curated or "").splitlines():
                        s = ln.strip().lstrip("-•*0123456789. \t")
                        if not s:
                            continue
                        if _is_garbage_fact(s):
                            continue
                        if 8 <= len(s) <= 200:
                            facts.append(s[:200])
                    seen: set[str] = set()
                    uniq: list[str] = []
                    for f in facts:
                        key = f.lower()
                        if key in seen:
                            continue
                        seen.add(key)
                        uniq.append(f)
                    if uniq:
                        self.bus.emit(
                            "pipeline.memory_curated",
                            {"facts": uniq[:3], "user_text": user_text},
                        )
                except Exception as exc:  # noqa: BLE001
                    self.bus.emit(
                        "pipeline.warning",
                        {"stage": "memory_store", "error": str(exc)},
                    )
        finally:
            self.emit_active(False)
