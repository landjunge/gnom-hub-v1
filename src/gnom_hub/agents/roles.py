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
                    hist_block = _format_brainstorm_history(hist)
                    return self.ask(
                        system=(
                            "You are the Brainstorm partner in Gnom-Hub.\n"
                            "Your job is FREE brainstorming with the user — not execution.\n"
                            "Rules:\n"
                            "- Match the user language (DE/EN).\n"
                            "- React to THIS message; build on earlier ideas in the history.\n"
                            "- Offer 3–6 concrete ideas, angles, or questions — not a finished plan.\n"
                            "- Ask at most ONE short follow-up if something is unclear.\n"
                            "- Do NOT start implementing, writing full code, or running the pipeline.\n"
                            "- Do NOT describe or redesign Gnom-Hub itself.\n"
                            "- No corporate fluff. Be direct and useful.\n"
                            "- If the user only refines (e.g. 'more on X'), go deeper on that — "
                            "do not restart from zero."
                        ),
                        user=_with_memory(
                            _brainstorm_user_payload(user_text, hist_block),
                            memory_ctx,
                        ),
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
            if self.has_llm():
                try:
                    raw = self.ask(
                        system=(
                            "You are the Coordinator assigning tasks. "
                            "Output exactly one line per worker: workerN | task. "
                            "No other text."
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
                        return tasks[:2]
                except Exception as exc:  # noqa: BLE001
                    self.bus.emit(
                        "pipeline.warning",
                        {"stage": "coordinate", "error": str(exc)},
                    )
            clean = [r for r in requirements if not r.startswith("Flex/")]
            t1 = f"Umsetzungsplan (Schritte) für: {user_text}"
            t2 = f"Konkretes Ergebnis-Artefakt für: {user_text}"
            if clean:
                t1 += "\n" + "\n".join(f"- {r}" for r in clean[:4])
                t2 += "\nFokus: " + clean[min(1, len(clean) - 1)]
            out: list[tuple[str, str]] = []
            for i, wid in enumerate(worker_ids[:2]):
                out.append((wid, t1 if i == 0 else t2))
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
                    return self.ask(
                        system=(
                            "You are a Worker agent. Deliver a concrete useful result "
                            "for the assigned task (plan, structure, checklist, draft, "
                            "or full HTML when the task is a page/UI). "
                            "If the task is HTML/landing/page: output ONE complete HTML "
                            "document starting with <!DOCTYPE html> (inline CSS/JS ok). "
                            "Work on the USER task only. Do not redefine Gnom-Hub. "
                            "No meta fluff. Match user language."
                        ),
                        user=_with_memory(body, memory_ctx),
                        max_tokens=1800,
                        temperature=0.5,
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


def _format_brainstorm_history(history: list[dict]) -> str:
    if not history:
        return ""
    lines: list[str] = []
    for turn in history[-12:]:
        role = str(turn.get("role") or "user")
        text = str(turn.get("text") or "").strip()
        if not text:
            continue
        label = "User" if role == "user" else "Brainstorm"
        lines.append(f"{label}: {text[:800]}")
    return "\n".join(lines)


def _brainstorm_user_payload(user_text: str, hist_block: str) -> str:
    if not hist_block:
        return f"USER MESSAGE:\n{user_text}"
    return (
        f"Earlier brainstorm dialogue:\n{hist_block}\n\n"
        f"Latest USER MESSAGE:\n{user_text}"
    )


def _stub_brainstorm(user_text: str, history: list[dict]) -> str:
    n = len([t for t in history if t.get("role") == "user"]) + 1
    if n <= 1:
        return (
            f"Ideen zu: {user_text}\n"
            "• Ziel und Nutzerwert in einem Satz schärfen\n"
            "• 3–5 Richtungen skizzieren (MVP vs. später)\n"
            "• Was darf bewusst weglassen werden?\n"
            "• Welches Ergebnis soll am Ende in Box 3 liegen?\n"
            "→ Was soll ich als Nächstes vertiefen?"
        )
    return (
        f"Weitergedacht (Runde {n}) zu: {user_text}\n"
        "• Vorherige Ideen enger zusammenführen\n"
        "• Eine Richtung priorisieren\n"
        "• Offene Frage klären, bevor wir ausführen\n"
        "→ Sag 'Execute' / klick Execute, wenn genug gesammelt ist — "
        "oder schreib weiter zum Feinschliff."
    )


def _with_memory(text: str, memory_ctx: str) -> str:
    ctx = _sanitize_memory_ctx(memory_ctx)
    if not ctx:
        return f"USER TASK (only this matters):\n{text}"
    return (
        f"USER TASK (only this matters):\n{text}\n\n"
        f"Optional background facts (ignore if unrelated or nonsense):\n{ctx[:600]}"
    )


def _sanitize_memory_ctx(memory_ctx: str) -> str:
    if not memory_ctx:
        return ""
    bad = (
        "localstorage",
        "notiz-speicher",
        "notizspeicher",
        "notes app",
        "ohne backend, der notizen",
        "json-array in localstorage",
        "json in localstorage",
        "responsive liste",
        "mini-notiz",
        "note storage",
        "notebook",
    )
    kept: list[str] = []
    for ln in memory_ctx.splitlines():
        low = ln.lower()
        if any(b in low for b in bad):
            continue
        if "gnom-hub" in low and ("ist ein" in low or "is a" in low or "is an" in low):
            continue
        kept.append(ln)
    return "\n".join(kept).strip()


def _is_garbage_fact(text: str) -> bool:
    low = text.lower()
    markers = (
        "localstorage",
        "notiz-speicher",
        "notizspeicher",
        "ohne backend",
        "json-array",
        "json in localstorage",
        "responsive liste",
        "notes app",
        "note storage",
        "mini-notiz",
        "notiztext",
    )
    return any(b in low for b in markers) or (
        "gnom-hub" in low and ("ist ein" in low or "is a" in low or "is an" in low)
    )


def _lines(raw: str) -> list[str]:
    out: list[str] = []
    for ln in (raw or "").splitlines():
        s = ln.strip().lstrip("-•*0123456789. \t")
        if len(s) > 3:
            out.append(s)
    return out


def _needs_clarify(text: str) -> bool:
    if "?" in text:
        return True
    return bool(re.search(r"\b(maybe|vielleicht|eventuell)\b", text, flags=re.IGNORECASE))
