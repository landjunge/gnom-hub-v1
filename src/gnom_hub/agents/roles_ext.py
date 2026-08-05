"""Coordinator, Worker, and Memory role agents."""

from __future__ import annotations

from typing import Any

from gnom_hub.agents.base import BaseAgent
from gnom_hub.agents.roles_helpers import (
    _is_garbage_fact,
    _lines,
    _needs_clarify,
    _with_memory,
)
from gnom_hub.core.event_bus import EventBus
from gnom_hub.pipeline.models import DistillQuestion


class CoordinatorAgent(BaseAgent):
    def distill(
        self, user_text: str, brainstorm: str, memory_ctx: str = ""
    ) -> tuple[list[str], DistillQuestion | None]:
        self.emit_active(True)
        try:
            reqs: list[str] | None = None
            if self.has_llm():
                try:
                    raw = self.ask(
                        system=(
                            "You are the Coordinator distilling the USER TASK into requirements. "
                            "Use the brainstorm dialogue as input. "
                            "Output ONLY 4–7 requirement lines for that task. No intro. "
                            "Prefer testable Definition-of-Done lines (observable behavior or "
                            "complete deliverable, e.g. full HTML with </html>). "
                            "Do not redefine Gnom-Hub. Match user language."
                        ),
                        user=_with_memory(
                            f"{user_text}\n\nBrainstorm dialogue:\n{brainstorm[:2500]}",
                            memory_ctx,
                        ),
                        max_tokens=400,
                        temperature=0.3,
                    )
                    reqs = _lines(raw) or [f"Ziel: {user_text}"]
                except Exception as exc:  # noqa: BLE001
                    self.bus.emit(
                        "pipeline.warning",
                        {"stage": "distill", "error": str(exc)},
                    )
            if not reqs:
                reqs = [
                    f"Ziel: {user_text}",
                    "MVP mit 3 Kernfunktionen",
                    "Klare Desktop-UI und lesbare Ausgaben",
                    "Fehler- und Leerzustände behandeln",
                ]
            question = None
            if _needs_clarify(user_text):
                question = DistillQuestion(
                    id="q1",
                    text="MVP/schnell oder gründlich/robust?",
                )
            return reqs[:8], question
        finally:
            self.emit_active(False)

    def plan(
        self,
        user_text: str,
        requirements: list[str],
        worker_ids: list[str],
    ) -> list[tuple[str, str]]:
        if not worker_ids:
            return []
        self.emit_active(True)
        try:
            blob = (user_text or "").lower()
            wants_one_page = any(
                k in blob
                for k in (
                    "html",
                    "landing",
                    "webpage",
                    "web page",
                    "website",
                    "seite",
                    "single file",
                    "single-file",
                )
            )
            if self.has_llm():
                try:
                    page_rule = ""
                    if wants_one_page:
                        page_rule = (
                            "CRITICAL for HTML/landing/page tasks: "
                            "Primary worker must deliver ONE complete single-file page "
                            "(<!DOCTYPE html>…</html>) with ALL requested sections "
                            "(e.g. hero + features + footer) in that same file. "
                            "Do NOT split hero/cards/footer into separate workers. "
                            "Extra workers: full-page variant, a11y polish, or QA checklist — "
                            "never incomplete section fragments.\n"
                        )
                    raw = self.ask(
                        system=(
                            "You are the Coordinator assigning tasks. "
                            "Output exactly one line per worker: workerN | task. "
                            "No other text.\n" + page_rule
                        ),
                        user=(
                            f"User: {user_text}\n"
                            f"Requirements:\n"
                            + "\n".join(f"- {r}" for r in requirements[:6])
                            + f"\nWorkers: {', '.join(worker_ids)}"
                        ),
                        max_tokens=300,
                        temperature=0.3,
                    )
                    tasks: list[tuple[str, str]] = []
                    for ln in raw.splitlines():
                        if "|" not in ln:
                            continue
                        left, right = ln.split("|", 1)
                        wid = left.strip().lower().replace(" ", "")
                        task = right.strip()
                        if wid in worker_ids and task:
                            tasks.append((wid, task))
                    if tasks:
                        return tasks[:4]
                except Exception as exc:  # noqa: BLE001
                    self.bus.emit(
                        "pipeline.warning",
                        {"stage": "coordinate", "error": str(exc)},
                    )
            clean = [r for r in requirements if not r.startswith("Flex/")]
            if wants_one_page:
                # Deterministic fallback: full page first, not section splits
                topic = (user_text or "").strip().rstrip(".")
                templates = [
                    (
                        f"ONE complete single-file HTML page for: {topic}. "
                        "Include ALL sections in the same file "
                        "(<!DOCTYPE html> … </html>). Functions first, minimal CSS."
                    ),
                    (
                        f"Full-page HTML VARIANT (still one complete file) for: {topic}. "
                        "Different layout/accent, same sections, must close </html>."
                    ),
                    f"QA checklist + interaction test plan for the landing page: {topic}",
                    f"Accessibility / empty-state notes for: {topic}",
                ]
            else:
                templates = [
                    f"Umsetzungsplan (Schritte) für: {user_text}",
                    f"Konkretes Ergebnis-Artefakt für: {user_text}",
                    f"Checkliste / QA für: {user_text}",
                    f"Alternativen / Edge-Cases für: {user_text}",
                ]
            if clean and not wants_one_page:
                templates[0] += "\n" + "\n".join(f"- {r}" for r in clean[:4])
                templates[1] += "\nFokus: " + clean[min(1, len(clean) - 1)]
            elif clean and wants_one_page:
                templates[0] += "\nDoD:\n" + "\n".join(f"- {r}" for r in clean[:4])
            out: list[tuple[str, str]] = []
            for i, wid in enumerate(worker_ids[:4]):
                out.append((wid, templates[i % len(templates)]))
            return out
        finally:
            self.emit_active(False)


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
                    # Reserve headroom so models can close </html> (token budget)
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
                            "Reserve the last ~15% of capacity to CLOSE the document "
                            "(</html>), not more styling.\n"
                            "If HTML/landing/page/UI:\n"
                            "  - ONE complete file: <!DOCTYPE html> … </html>\n"
                            "  - At least one real interaction "
                            "(onclick= or addEventListener or form submit handler)\n"
                            "  - Prefer working demo over pretty design\n"
                            "BEFORE SUBMIT checklist:\n"
                            "  [ ] ends with </html> (if HTML)\n"
                            "  [ ] tags/braces closed\n"
                            "  [ ] core functions present (not only empty-state markup)\n"
                            "  [ ] no truncation mid-CSS/JS\n"
                            "Work on the USER task only. Do not redefine Gnom-Hub. "
                            "No meta fluff. Match user language."
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
            if not raw:
                return ""
            if not self.has_llm() or not user_text.strip():
                return raw[:900]
            try:
                curated = self.ask(
                    system=(
                        "You are the Memory agent. From the stored context, select only "
                        "what is relevant for the current user task. "
                        "Output 3–8 short bullet facts. No preamble. "
                        "If nothing is relevant, output: (no relevant memory)"
                    ),
                    user=f"Task:\n{user_text}\n\nStored context:\n{raw[:2500]}",
                    max_tokens=350,
                    temperature=0.2,
                )
                return curated or raw[:900]
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
            clean_reqs = [r for r in requirements if not r.startswith("Flex/") and len(r) < 160][:5]
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
                    pack = (
                        f"User: {user_text}\n"
                        f"Requirements:\n"
                        + "\n".join(f"- {r}" for r in clean_reqs)
                        + f"\nBrainstorm (head):\n{(brainstorm or '')[:600]}\n"
                        f"Worker results (head):\n"
                        + "\n---\n".join((r or "")[:400] for r in results[:2])
                    )
                    curated = self.ask(
                        system=(
                            "You are the Memory agent curating long-term facts. "
                            "Extract 1–3 durable facts worth remembering. "
                            "One fact per line. No intro. If nothing: (none)"
                        ),
                        user=pack,
                        max_tokens=200,
                        temperature=0.2,
                    )
                    facts: list[str] = []
                    for ln in (curated or "").splitlines():
                        s = ln.strip().lstrip("-•* ")
                        if not s or s.lower() in ("(none)", "none", "n/a"):
                            continue
                        if len(s) > 8:
                            facts.append(s[:200])
                    facts = [f for f in facts if not _is_garbage_fact(f)]
                    if facts:
                        self.bus.emit(
                            "pipeline.memory_curated",
                            {"facts": facts[:3], "user_text": user_text},
                        )
                except Exception as exc:  # noqa: BLE001
                    self.bus.emit(
                        "pipeline.warning",
                        {"stage": "memory_store", "error": str(exc)},
                    )
        finally:
            self.emit_active(False)
