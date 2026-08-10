"""Worker and Memory role agents."""

from __future__ import annotations

from typing import Any

from gnom_hub.agents.base import BaseAgent
from gnom_hub.agents.roles_helpers import (
    _is_flex_meta_requirement,
    _is_garbage_fact,
    _with_memory,
)
from gnom_hub.config.auth import user_message_for_failure
from gnom_hub.core.event_bus import EventBus

# ── Worker prompt layers (see docs/WORKER_PROMPTS.md) ─────────────────
# L0 HUB_IDENTITY is injected by BaseAgent.ask
# L1 Role contract
# L2 Priority / budget
# L3 Domain (HTML) rules
# L4 Flex wishes (absolute)
# L5 Tool protocol (prefetch is authoritative)

_WORKER_L1_ROLE = (
    "You are a Worker agent inside Gnom-Hub. "
    "Deliver a concrete useful result for the assigned task "
    "(plan, structure, checklist, draft, or full HTML when the task is a page/UI).\n"
    "Work on the USER task only. Match user language.\n"
    "If you cannot complete the task honestly (missing data, impossible constraint), "
    "start the body with FEHLER and explain — never invent a fake success stub."
)

_WORKER_L2_PRIORITY = (
    "PRIORITY ORDER (mandatory — do not reverse):\n"
    "  1) Complete structure / skeleton (always finish the file)\n"
    "  2) Core interactive behavior (JS/handlers, DOM updates)\n"
    "  3) Error/empty states for those core flows\n"
    "  4) CSS/styling LAST (max ~30% of effort; minimal layout first)\n"
    "Budget: ~70% functions+structure, ~30% styling. If near limit, "
    "CUT CSS — never omit </html> or core interactions."
)

_WORKER_L3_HTML = (
    "If HTML/landing/page/UI:\n"
    "  - ONE complete file: <!DOCTYPE html> ... </html>\n"
    "  - At least one real interaction "
    "(onclick= or addEventListener or form submit handler)\n"
    "  - Prefer working demo over pretty design\n"
    "  - DESIGN TOOLS (when present in Tool prefetch):\n"
    "      * Use color_palette CSS variables (--color-primary, --color-surface, …)\n"
    "      * Prefer html_scaffold structure as starting skeleton if provided\n"
    "      * Run contrast_check mentally: text on surface must stay readable\n"
    "      * Do NOT invent a second palette — reuse the prefetched one\n"
    "  - Without design prefetch: still use CSS variables and a dark-friendly default"
)

_WORKER_L4_WISHES = (
    "STANDING USER WISHES (Flex-wish / User: lines) are ABSOLUTE ORDERS:\n"
    "  - Implement them fully in the deliverable — no debate, no skip,\n"
    "    no 'optional', no 'if space allows'.\n"
    "  - Do not contradict, weaken, or postpone them.\n"
    "  - If a wish conflicts with decoration, drop decoration, keep the wish.\n"
    "  - Dark theme / language / always-rules must be visible in the result."
)

_WORKER_L5_TOOLS = (
    "TOOL PROTOCOL:\n"
    "  - The hub may inject a block \"Tool prefetch (auto):\" with real tool outputs "
    "(web_fetch, memory_search, install_tool, color_palette, html_scaffold, …).\n"
    "  - Treat that block as ground truth. Cite URLs/facts from it; do not contradict it.\n"
    "  - You do not call tools yourself mid-turn — the hub prefetches. "
    "If a needed tool result is missing, work without inventing network data.\n"
    "  - When install_tool reports a package installed, you may assume the import exists "
    "in later runtime (do not claim you ran the install)."
)


def worker_system_prompt(*, wants_html: bool = False) -> str:
    """Assemble layered worker system prompt (L1–L5)."""
    parts = [
        _WORKER_L1_ROLE,
        _WORKER_L2_PRIORITY,
        _WORKER_L4_WISHES,
        _WORKER_L5_TOOLS,
    ]
    if wants_html:
        parts.insert(2, _WORKER_L3_HTML)
    return "\n".join(parts)


def task_wants_html(*blobs: str) -> bool:
    text = "\n".join(blobs).lower()
    return any(
        k in text
        for k in (
            "html",
            "landing",
            "webpage",
            "web page",
            "css",
            "seite",
            "website",
            "frontend",
            "dashboard",
            "ui page",
            "web design",
        )
    )


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
            task_lines = [ln.strip() for ln in (task or "").splitlines() if ln.strip()]
            task_head = task_lines[0][:140] if task_lines else "(empty task)"
            if not self.has_llm():
                why = user_message_for_failure("DEEPSEEK_API_KEY missing", role=self.id)
                return (
                    f"{self.state.name} FEHLER - kein Deliverable\n"
                    f"Aufgabe: {task_head}\n"
                    f"{why}\n"
                    "Kein Fake-Ergebnis. Worker liefert erst mit gueltigem Provider."
                )
            try:
                body = f"Aufgabe: {task}\nOriginal: {user_text}\nAnforderungen:\n" + "\n".join(
                    f"- {r}" for r in requirements[:12]
                )
                wants_html = task_wants_html(task, user_text, "\n".join(requirements[:12]))
                max_tok = 3200 if wants_html else 1800
                return self.ask(
                    system=worker_system_prompt(wants_html=wants_html),
                    user=_with_memory(body, memory_ctx),
                    max_tokens=max_tok,
                    temperature=0.45,
                )
            except Exception as exc:  # noqa: BLE001
                err = str(exc)
                self.bus.emit(
                    "pipeline.warning",
                    {"stage": self.id, "error": err, "kind": "llm"},
                )
                note = getattr(self.llm, "note_auth_failure", None)
                if callable(note) and (
                    "401" in err or "403" in err or type(exc).__name__ == "AuthError"
                ):
                    try:
                        note(getattr(self.state, "api_key", None))
                    except Exception:  # noqa: BLE001
                        pass
                why = user_message_for_failure(exc, role=self.id)
                return (
                    f"{self.state.name} FEHLER - kein Deliverable\n"
                    f"Aufgabe: {task_head}\n"
                    f"{why}\n"
                    "Kein Stub-Ersatz. Key pruefen, Budget pruefen, dann erneut ausfuehren."
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
